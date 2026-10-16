"""Full-history and working-tree release auditor for open-source publication.

Scans the repository for compliance with docs/DATA_POLICY.md:
1. Media & Assets: audio, images, Live2D files, oversized JSONs.
2. Secrets & Tokens: API keys, private keys, access tokens.
3. Private network addresses & sensitive paths: private IPs, personal user paths, NAS paths.
4. Working tree & historical commits: verifies clean history from initial commit to HEAD.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Suffixes forbidden in committed repo
AUDIO_SUFFIXES = frozenset({".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"})
IMAGE_SUFFIXES = frozenset(
    {".avif", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".tif", ".tiff", ".webp"}
)
LIVE2D_SUFFIXES = frozenset(
    {
        ".atlas",
        ".cdi3.json",
        ".exp3.json",
        ".moc",
        ".moc3",
        ".model3.json",
        ".motion3.json",
        ".physics3.json",
        ".skel",
        ".userdata3.json",
    }
)
MAX_JSON_BYTES = 1 * 1024 * 1024
LARGE_JSON_ALLOWLIST = ("data", "tests/fixtures")

# Secret regex patterns
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenAI API Key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Anthropic API Key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub Personal Access Token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "Private Key Header",
        re.compile(r"-----BEGIN\s+(RSA|DSA|EC|OPENSSH|PGP)?\s*PRIVATE\s+KEY-----"),
    ),
    (
        "Generic High-Entropy Token Assignment",
        re.compile(
            r"""(?i)(?:api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|password)\s*[:=]\s*['"][A-Za-z0-9_\-+=]{24,}['"]"""
        ),
    ),
)

# Sensitive network and host paths
SENSITIVE_HOST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Private RFC 1918 / CGNAT / Tailscale IPv4 addresses
    (
        "Private IPv4 Address",
        re.compile(
            r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}|100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.\d{1,3}\.\d{1,3})\b"
        ),
    ),
    (
        "Internal NAS Path",
        re.compile(r"/(?:volume[1-9]|share|mnt/nas)/[a-zA-Z0-9_-]+"),
    ),
    (
        "Local Personal User Path",
        re.compile(
            r"""(?:[A-Za-z]:\\Users\\[a-zA-Z0-9_]+|/Users/[a-zA-Z0-9_]+|/home/[a-zA-Z0-9_]+)"""
        ),
    ),
)

# Safe allowances / placeholders in documentation, examples, and tests
ALLOWED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"your[_-]?(?:api[_-]?key|token|secret|password)", re.IGNORECASE),
    re.compile(
        r"(?:change[_-]?me|example|dummy|placeholder|sample|mock|test_secret)", re.IGNORECASE
    ),
    re.compile(r"sk-[A-Za-z0-9]*\.{3,}", re.IGNORECASE),
    re.compile(r"gh[op]_[*]+", re.IGNORECASE),
    re.compile(r"gho_[*]+", re.IGNORECASE),
    re.compile(r"<[A-Za-z0-9_-]+>", re.IGNORECASE),
    # RFC 5737 / documentation IP examples or masks
    re.compile(r"192\.168\.[xX*]+", re.IGNORECASE),
    re.compile(r"10\.[xX*]+", re.IGNORECASE),
    re.compile(r"127\.0\.0\.1"),
    re.compile(r"0\.0\.0\.0"),
)


@dataclass(frozen=True, slots=True)
class AuditViolation:
    category: str
    target: str
    detail: str
    commit: str = ""


@dataclass
class AuditReport:
    total_commits: int = 0
    scanned_commits: int = 0
    scanned_files: int = 0
    scanned_diff_lines: int = 0
    violations: list[AuditViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "total_commits": self.total_commits,
            "scanned_commits": self.scanned_commits,
            "scanned_files": self.scanned_files,
            "scanned_diff_lines": self.scanned_diff_lines,
            "violation_count": len(self.violations),
            "violations": [asdict(v) for v in self.violations],
        }

    def to_markdown(self) -> str:
        status_line = (
            "PASS (0 violations)" if self.passed else f"FAIL ({len(self.violations)} violations)"
        )
        lines = [
            "# M6 Release Audit Report",
            "",
            f"**Audit Status**: {status_line}",
            f"- **Total Historical Commits Scanned**: {self.scanned_commits} / {self.total_commits}",
            f"- **Working Tree Files Scanned**: {self.scanned_files}",
            f"- **Diff Lines Audited**: {self.scanned_diff_lines}",
            f"- **Violations Found**: {len(self.violations)}",
            "",
            "## Findings",
        ]
        if self.passed:
            lines.append(
                "No violations found. Repository history and current working tree comply with docs/DATA_POLICY.md."
            )
        else:
            lines.append("| Category | Target | Commit | Detail |")
            lines.append("|---|---|---|---|")
            for v in self.violations:
                lines.append(
                    f"| {v.category} | {v.target} | {v.commit or 'working-tree'} | {v.detail} |"
                )
        lines.append("")
        return "\n".join(lines)


def _is_safe_text(match_text: str) -> bool:
    for allowed in ALLOWED_PATTERNS:
        if allowed.search(match_text):
            return True
    return False


def check_file_path(path_str: str) -> str | None:
    path_lower = path_str.lower().replace("\\", "/")
    if path_lower.startswith("data/") or path_lower == "data":
        return None

    for live2d_ext in LIVE2D_SUFFIXES:
        if path_lower.endswith(live2d_ext):
            return f"Live2D file format '{live2d_ext}' is forbidden in repository"

    candidate_suffix = Path(path_lower).suffix
    if candidate_suffix in AUDIO_SUFFIXES:
        return f"Audio media '{candidate_suffix}' is forbidden in repository"
    if candidate_suffix in IMAGE_SUFFIXES:
        return f"Image media '{candidate_suffix}' is forbidden in repository"

    return None


def audit_content_line(line: str, source_desc: str, commit_sha: str = "") -> list[AuditViolation]:
    violations: list[AuditViolation] = []
    # Test for secrets
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(line):
            matched_str = match.group(0)
            if not _is_safe_text(matched_str) and not _is_safe_text(line):
                masked = matched_str[:4] + "***" if len(matched_str) > 8 else "***"
                violations.append(
                    AuditViolation(
                        category="Secret / Token",
                        target=source_desc,
                        detail=f"Detected potential {name}: {masked}",
                        commit=commit_sha,
                    )
                )

    # Test for sensitive host/network
    for name, pattern in SENSITIVE_HOST_PATTERNS:
        for match in pattern.finditer(line):
            matched_str = match.group(0)
            if not _is_safe_text(matched_str) and not _is_safe_text(line):
                violations.append(
                    AuditViolation(
                        category="Network / Path Leak",
                        target=source_desc,
                        detail=f"Detected potential {name}: {matched_str}",
                        commit=commit_sha,
                    )
                )

    return violations


def audit_git_history(root: Path) -> tuple[int, int, list[AuditViolation]]:
    """Scan all git commits for forbidden files, secrets, and leaks."""
    violations: list[AuditViolation] = []
    lines_scanned = 0

    log_cmd = subprocess.run(
        ["git", "-C", str(root), "log", "--reverse", "--format=%H %s"],
        capture_output=True,
        text=True,
        check=True,
    )
    commit_lines = [line.strip() for line in log_cmd.stdout.splitlines() if line.strip()]
    total_commits = len(commit_lines)

    for entry in commit_lines:
        sha, _, subject = entry.partition(" ")
        short_sha = sha[:8]

        # 1. Check tree/filenames added or modified in this commit
        diff_tree = subprocess.run(
            ["git", "-C", str(root), "diff-tree", "-r", "--no-commit-id", "--name-status", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in diff_tree.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                status, file_path = parts[0], parts[1]
                if status != "D":
                    file_violation = check_file_path(file_path)
                    if file_violation:
                        violations.append(
                            AuditViolation(
                                category="Asset / Media Guard",
                                target=file_path,
                                detail=file_violation,
                                commit=short_sha,
                            )
                        )

        # 2. Check diff text for secrets and leaks
        diff_show = subprocess.run(
            ["git", "-C", str(root), "show", "--format=", "-p", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        current_file = ""
        for line in diff_show.stdout.splitlines():
            lines_scanned += 1
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                continue
            if line.startswith("+") and not line.startswith("+++"):
                added_content = line[1:]
                source_desc = (
                    f"{current_file} (commit {short_sha})"
                    if current_file
                    else f"commit {short_sha}"
                )
                violations.extend(audit_content_line(added_content, source_desc, short_sha))

    return total_commits, lines_scanned, violations


def audit_working_tree(root: Path) -> tuple[int, list[AuditViolation]]:
    """Scan working-tree tracked and untracked non-ignored files."""
    violations: list[AuditViolation] = []
    ls_files = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        check=True,
    )
    paths = [Path(p) for p in ls_files.stdout.decode("utf-8").split("\0") if p]
    file_count = len(paths)

    for rel_path in paths:
        path_str = rel_path.as_posix()
        file_violation = check_file_path(path_str)
        if file_violation:
            violations.append(
                AuditViolation(
                    category="Asset / Media Guard",
                    target=path_str,
                    detail=file_violation,
                    commit="",
                )
            )
            continue

        full_path = root / rel_path
        if not full_path.is_file():
            continue

        # File size check for JSON
        if path_str.lower().endswith(".json"):
            size = full_path.stat().st_size
            if size > MAX_JSON_BYTES and not any(
                path_str.startswith(a) for a in LARGE_JSON_ALLOWLIST
            ):
                violations.append(
                    AuditViolation(
                        category="Asset / Media Guard",
                        target=path_str,
                        detail=f"Oversized JSON ({size / (1024 * 1024):.2f} MiB > {MAX_JSON_BYTES // (1024 * 1024)} MiB)",
                        commit="",
                    )
                )

        # Content scanning for plain text files
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, start=1):
                    source_desc = f"{path_str}:{line_idx}"
                    violations.extend(audit_content_line(line, source_desc, ""))
        except Exception as e:
            violations.append(
                AuditViolation(
                    category="Read Error",
                    target=path_str,
                    detail=f"Failed to read file: {e}",
                    commit="",
                )
            )

    return file_count, violations


def run_audit(root: Path, check_history: bool = True, check_working: bool = True) -> AuditReport:
    report = AuditReport()
    if check_history:
        total_commits, lines_scanned, history_violations = audit_git_history(root)
        report.total_commits = total_commits
        report.scanned_commits = total_commits
        report.scanned_diff_lines = lines_scanned
        report.violations.extend(history_violations)

    if check_working:
        scanned_files, working_violations = audit_working_tree(root)
        report.scanned_files = scanned_files
        report.violations.extend(working_violations)

    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root path")
    parser.add_argument("--history-only", action="store_true", help="Only audit Git history")
    parser.add_argument("--working-only", action="store_true", help="Only audit working tree")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--markdown", action="store_true", help="Output Markdown report format")
    parser.add_argument("--out", type=Path, help="Write output report to file")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    check_history = not args.working_only
    check_working = not args.history_only

    report = run_audit(root, check_history=check_history, check_working=check_working)

    if args.json:
        out_text = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    elif args.markdown:
        out_text = report.to_markdown()
    else:
        status_msg = "PASSED" if report.passed else f"FAILED ({len(report.violations)} violations)"
        out_text = (
            f"Release Audit: {status_msg}\n"
            f"Commits scanned: {report.scanned_commits}\n"
            f"Files scanned: {report.scanned_files}\n"
            f"Diff lines audited: {report.scanned_diff_lines}\n"
        )
        if not report.passed:
            out_text += "\nViolations:\n"
            for v in report.violations:
                out_text += f"- [{v.category}] {v.target} (commit: {v.commit or 'working-tree'}): {v.detail}\n"

    if args.out:
        args.out.write_text(out_text, encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(out_text)

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
