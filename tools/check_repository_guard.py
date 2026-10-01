"""Reject committed media, Live2D files, and oversized JSON outside allowlists."""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_JSON_BYTES = 1 * 1024 * 1024
LOCAL_DATA_PREFIX = "data"
LARGE_JSON_ALLOWLIST = ("data", "tests/fixtures")

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


@dataclass(frozen=True, slots=True)
class Violation:
    """One repository guard finding."""

    path: str
    reason: str


def _normalise(relative_path: Path) -> str:
    return relative_path.as_posix().casefold().removeprefix("./")


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def _is_allowed_large_json(path: str) -> bool:
    return any(_under(path, prefix) for prefix in LARGE_JSON_ALLOWLIST)


def scan_paths(root: Path, relative_paths: Iterable[Path]) -> list[Violation]:
    """Scan explicit paths relative to ``root``.

    ``data/`` is intentionally skipped because it is the private local data
    root. Large synthetic JSON fixtures are allowed only in
    ``tests/fixtures/``; no committed directory is allowed to contain media.
    """

    root = root.resolve()
    violations: list[Violation] = []
    for relative_path in relative_paths:
        candidate = (root / relative_path).resolve()
        try:
            safe_relative = candidate.relative_to(root)
        except ValueError:
            violations.append(
                Violation(str(relative_path), "path resolves outside repository root")
            )
            continue

        path = _normalise(safe_relative)
        if _under(path, LOCAL_DATA_PREFIX) or not candidate.is_file():
            continue

        matched_live2d = next((suffix for suffix in LIVE2D_SUFFIXES if path.endswith(suffix)), None)
        if matched_live2d:
            violations.append(
                Violation(path, f"Live2D file suffix {matched_live2d!r} is not allowed")
            )
            continue

        suffix = candidate.suffix.lower()
        if suffix in AUDIO_SUFFIXES:
            violations.append(Violation(path, f"audio file suffix {suffix!r} is not allowed"))
            continue
        if suffix in IMAGE_SUFFIXES:
            violations.append(Violation(path, f"image file suffix {suffix!r} is not allowed"))
            continue
        if (
            suffix == ".json"
            and candidate.stat().st_size > MAX_JSON_BYTES
            and not _is_allowed_large_json(path)
        ):
            size_mib = candidate.stat().st_size / (1024 * 1024)
            violations.append(
                Violation(
                    path,
                    f"JSON is {size_mib:.2f} MiB; files over {MAX_JSON_BYTES // (1024 * 1024)} MiB "
                    "must stay in an allowlisted fixture/data directory",
                )
            )

    return violations


def tracked_paths(root: Path) -> list[Path]:
    """Return tracked and non-ignored working-tree paths."""

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    return [Path(item) for item in result.stdout.decode("utf-8").split("\0") if item]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="repository root (default: current directory)"
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        type=Path,
        help="explicit paths relative to --root; useful for testing an untracked candidate",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    root = args.root.resolve()
    paths = args.paths if args.paths else tracked_paths(root)
    violations = scan_paths(root, paths)
    if violations:
        print("Repository guard failed:")
        for violation in violations:
            print(f"- {violation.path}: {violation.reason}")
        return 1

    print(f"Repository guard passed: scanned {len(paths)} tracked/non-ignored file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
