#!/usr/bin/env python3
"""Entry point for running the persona pipeline from repository root."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipeline.cli import main

if __name__ == "__main__":
    sys.exit(main())
