from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.audit_release import (
    AuditReport,
    audit_content_line,
    check_file_path,
    run_audit,
)


class TestAuditRelease(unittest.TestCase):
    def test_check_file_path_media(self) -> None:
        self.assertIsNotNone(check_file_path("assets/voice.mp3"))
        self.assertIsNotNone(check_file_path("images/card.png"))
        self.assertIsNotNone(check_file_path("live2d/model.moc3"))
        self.assertIsNotNone(check_file_path("live2d/character.model3.json"))

    def test_check_file_path_allowed(self) -> None:
        self.assertIsNone(check_file_path("README.md"))
        self.assertIsNone(check_file_path("server/src/main.py"))
        self.assertIsNone(check_file_path("data/character_voice.mp3"))
        self.assertIsNone(check_file_path("data/images/card.png"))

    def test_audit_content_line_secret_detection(self) -> None:
        fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
        violations = audit_content_line(f"API_KEY = '{fake_key}'", "test.py:1")
        self.assertTrue(any("OpenAI API Key" in v.detail for v in violations))

        fake_ghp = "ghp_" + "111122223333444455556666777788889999"
        violations = audit_content_line(f"token: {fake_ghp}", "test.py:2")
        self.assertTrue(any("GitHub Personal Access Token" in v.detail for v in violations))

        fake_privkey = "-----" + "BEGIN RSA PRIVATE KEY" + "-----"
        violations = audit_content_line(fake_privkey, "test.key:1")
        self.assertTrue(any("Private Key Header" in v.detail for v in violations))

    def test_audit_content_line_safe_placeholders(self) -> None:
        safe_lines = [
            "OPENAI_API_KEY=your-api-key-here",
            "sk-...",
            "gho_************************************",
            "MODEL_GATEWAY_API_KEY=dummy_placeholder",
            "password = 'change-me'",
            "curl http://127.0.0.1:8000",
            "listen 0.0.0.0:8000",
            "ip: 192.168.x.x",
        ]
        for line in safe_lines:
            violations = audit_content_line(line, "safe.py:1")
            self.assertEqual(
                len(violations), 0, f"Expected safe line to have no violations: {line}"
            )

    def test_audit_content_line_leak_detection(self) -> None:
        fake_ip = "192.168." + "1.150"
        violations = audit_content_line(f"HOST={fake_ip}", "conf.py:1")
        self.assertTrue(any("Private IPv4 Address" in v.detail for v in violations))

        fake_nas = "/volume" + "1/docker/data"
        violations = audit_content_line(f"path = '{fake_nas}'", "conf.py:2")
        self.assertTrue(any("Internal NAS Path" in v.detail for v in violations))

    def test_audit_report_format(self) -> None:
        report = AuditReport(
            total_commits=10, scanned_commits=10, scanned_files=20, scanned_diff_lines=500
        )
        self.assertTrue(report.passed)
        md = report.to_markdown()
        self.assertIn("PASS (0 violations)", md)
        self.assertIn("10 / 10", md)

    def test_run_audit_on_clean_temp_repo(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        report = run_audit(repo_root, check_history=True, check_working=True)
        self.assertTrue(report.passed)
        self.assertGreaterEqual(report.total_commits, 1)
        self.assertEqual(len(report.violations), 0)

    def test_check_file_path_forbidden_directories(self) -> None:
        self.assertIsNotNone(check_file_path("deploy/secrets/fcm.json"))
        self.assertIsNotNone(check_file_path("private-data/ratings.json"))

    def test_audit_content_line_does_not_whitelist_entire_line(self) -> None:
        fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
        line_with_example = f"API_KEY = '{fake_key}'  # see example config"
        violations = audit_content_line(line_with_example, "test.py:1")
        self.assertTrue(any("OpenAI API Key" in v.detail for v in violations))

        fake_ip = "192.168." + "1.150"
        line_with_placeholder = f"HOST={fake_ip}  # placeholder host"
        violations_ip = audit_content_line(line_with_placeholder, "test.py:2")
        self.assertTrue(any("Private IPv4 Address" in v.detail for v in violations_ip))


class TestAuditReleaseGitPaths(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="juus-audit-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.tool = Path(__file__).resolve().parents[1] / "tools" / "audit_release.py"
        self.git("init", "-q")
        self.git("config", "user.name", "Audit Test")
        self.git("config", "user.email", "audit@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(self.root / "no-hooks"))

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout

    def add_file(self, path: str) -> None:
        (self.root / path).write_text("Fictional audit fixture.\n", encoding="utf-8")
        self.git("add", "--", path)
        self.git("commit", "-qm", "Add synthetic fixture")

    def audit_cli(self, mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.tool), "--root", str(self.root), mode, "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def assert_image_violation(self, result: subprocess.CompletedProcess[str], path: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        violations = json.loads(result.stdout)["violations"]
        self.assertTrue(
            any(v["target"] == path and "'.png'" in v["detail"] for v in violations),
            result.stdout,
        )

    def test_history_rejects_deleted_image_with_spaces(self) -> None:
        self.add_file("my cover.png")
        self.git("rm", "--", "my cover.png")
        self.git("commit", "-qm", "Remove synthetic fixture")
        self.assert_image_violation(self.audit_cli("--history-only"), "my cover.png")

    def test_history_rejects_deleted_image_without_spaces(self) -> None:
        self.add_file("cover.png")
        self.git("rm", "--", "cover.png")
        self.git("commit", "-qm", "Remove synthetic fixture")
        self.assert_image_violation(self.audit_cli("--history-only"), "cover.png")

    def test_history_allows_markdown(self) -> None:
        self.add_file("readme.md")
        result = self.audit_cli("--history-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["violations"], [])

    def test_history_rejects_rename_to_image_with_spaces(self) -> None:
        self.add_file("readme.md")
        self.git("mv", "readme.md", "my cover.png")
        self.git("commit", "-qm", "Rename synthetic fixture")
        self.assert_image_violation(self.audit_cli("--history-only"), "my cover.png")

    def test_history_allows_rename_to_markdown_with_spaces(self) -> None:
        self.add_file("readme.md")
        self.git("mv", "readme.md", "my readme.md")
        self.git("commit", "-qm", "Rename synthetic fixture")
        result = self.audit_cli("--history-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["violations"], [])

    def test_working_tree_rejects_image_with_spaces(self) -> None:
        self.add_file("my cover.png")
        result = self.audit_cli("--working-only")
        self.assert_image_violation(result, "my cover.png")
        self.assertEqual(json.loads(result.stdout)["violations"][0]["commit"], "")

    def test_history_checks_both_paths_in_rename_and_copy_records(self) -> None:
        original_run = subprocess.run

        def detect_renames_and_copies(command: list[str], **kwargs):
            # Plumbing diff-tree needs explicit flags to emit R/C records.
            if "--name-status" in command:
                command = [*command, "-M", "-C", "--find-copies-harder"]
            return original_run(command, **kwargs)

        self.add_file("old cover.png")
        self.git("mv", "old cover.png", "renamed cover.png")
        self.git("commit", "-qm", "Rename synthetic fixture")
        rename_sha = self.git("rev-parse", "--short=8", "HEAD").strip()
        self.assertTrue(
            self.git("diff-tree", "-r", "--no-commit-id", "--name-status", "-M", "HEAD").startswith(
                "R100\t"
            )
        )

        (self.root / "copied cover.png").write_bytes((self.root / "renamed cover.png").read_bytes())
        self.git("add", ".")
        self.git("commit", "-qm", "Copy synthetic fixture")
        copy_sha = self.git("rev-parse", "--short=8", "HEAD").strip()
        self.assertTrue(
            self.git(
                "diff-tree",
                "-r",
                "--no-commit-id",
                "--name-status",
                "-C",
                "--find-copies-harder",
                "HEAD",
            ).startswith("C100\t")
        )

        with patch("tools.audit_release.subprocess.run", side_effect=detect_renames_and_copies):
            report = run_audit(self.root, check_working=False)
        image_paths = {
            (violation.commit, violation.target)
            for violation in report.violations
            if "'.png'" in violation.detail
        }
        self.assertIn((rename_sha, "old cover.png"), image_paths)
        self.assertIn((rename_sha, "renamed cover.png"), image_paths)
        self.assertIn((copy_sha, "renamed cover.png"), image_paths)
        self.assertIn((copy_sha, "copied cover.png"), image_paths)


if __name__ == "__main__":
    unittest.main()
