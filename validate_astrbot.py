#!/usr/bin/env python3
"""CLI script to validate AstrBot persona files against AstrBot upstream specifications."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.validator.astrbot import validate_astrbot_dir, validate_astrbot_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AstrBot persona JSON files against AstrBot schema.")
    parser.add_argument("path", type=Path, help="Path to an AstrBot JSON file or directory")
    args = parser.parse_args()

    target = args.path
    if not target.exists():
        print(f"Error: Path {target} does not exist.")
        return 1

    if target.is_file():
        res = validate_astrbot_file(target)
        for r in res.results:
            icon = "✓" if r.passed else "✗"
            print(f"[{icon}] {target.name}: {r.message}")
        return 0 if res.passed else 1

    # Directory
    total, passed, results = validate_astrbot_dir(target)
    print(f"Validated {total} AstrBot persona files in {target}: {passed}/{total} passed.")
    failed = [r for r in results if not r.passed]
    for f in failed:
        for r in f.results:
            print(f"  [FAIL] {f.file_path.name}: {r.message}")

    return 0 if (total > 0 and passed == total) else (0 if total == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
