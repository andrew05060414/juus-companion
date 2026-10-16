from __future__ import annotations

from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
