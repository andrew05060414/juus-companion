"""Exporter for Juus Brain intermediate format (aligned with #3 specifications)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from pipeline.extractor.models import CharacterRawMaterial
from pipeline.generator.lorebook import assemble_three_layer_lorebook


def export_juus_brain_format(
    card_data: Dict,
    raw: CharacterRawMaterial,
    output_path: Path,
) -> Path:
    """Export unified Juus Brain intermediate schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lorebook_layers = assemble_three_layer_lorebook(raw)
    data = card_data.get("data", {})
    ext = data.get("extensions", {})
    game_state = ext.get("game_state", {})

    brain_doc = {
        "schema_version": "1.0",
        "character_id": raw.astrbot_id,
        "ship_group": raw.ship_group,
        "name_cn": raw.name_cn,
        "name_en": raw.name_en,
        "faction_key": raw.faction_key,
        "faction_cn": raw.faction_cn,
        "baseline_relationship": {
            "level": game_state.get("level", 125),
            "affinity": game_state.get("affinity", 200),
            "is_oath": game_state.get("is_oath", True),
        },
        "persona_spec": card_data,
        "lorebook_layers": lorebook_layers,
        "raw_stats": {
            "chat_topics_count": raw.stats.chat_topics_count,
            "chat_lines_count": raw.stats.chat_lines_count,
            "juus_posts_count": raw.stats.juus_posts_count,
            "juus_comments_made_count": raw.stats.juus_comments_made_count,
            "total_voicelines_count": raw.stats.total_voicelines_count,
            "oath_and_ex_voicelines_count": raw.stats.oath_and_ex_voicelines_count,
            "audio_links_count": raw.stats.audio_links_count,
            "memories_count": raw.stats.memories_count,
        },
        "notes": raw.notes,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(brain_doc, f, ensure_ascii=False, indent=2)

    return output_path

