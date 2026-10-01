"""Exporter for SillyTavern V2 character card and standalone Lorebook."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def export_sillytavern_card(card_data: Dict, output_path: Path) -> Path:
    """Export SillyTavern V2 card to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(card_data, f, ensure_ascii=False, indent=2)
    return output_path


def export_standalone_lorebook(lorebook_data: Dict, output_path: Path) -> Path:
    """Export standalone Lorebook to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(lorebook_data, f, ensure_ascii=False, indent=2)
    return output_path

