"""Exporter for AstrBot Persona format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def export_astrbot_persona(persona_data: Dict, output_path: Path) -> Path:
    """Export AstrBot persona to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(persona_data, f, ensure_ascii=False, indent=2)
    return output_path


def export_astrbot_persona_names(names_map: Dict[str, str], output_path: Path) -> Path:
    """Export sidecar persona name mapping (persona_id -> name_cn) as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(names_map, f, ensure_ascii=False, indent=2)
    return output_path
