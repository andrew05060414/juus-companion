"""Tests for exporter formats: SillyTavern, AstrBot, and Juus Brain."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.exporter.astrbot import export_astrbot_persona
from pipeline.exporter.brain import export_juus_brain_format
from pipeline.exporter.sillytavern import export_sillytavern_card, export_standalone_lorebook
from pipeline.extractor.models import CharacterRawMaterial


def test_exporters_write_valid_json(tmp_path: Path):
    raw = CharacterRawMaterial(
        ship_group=66666,
        name_cn="虚构巡航舰",
        name_en="Fictional Cruiser",
        astrbot_id="fictional_cruiser",
        faction_key="royal_navy",
        faction_cn="皇家",
    )
    raw.calculate_stats()

    card_data = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "虚构巡航舰",
            "extensions": {"game_state": {"level": 125, "affinity": 200, "is_oath": True}},
        },
    }

    # 1. SillyTavern Card
    st_path = tmp_path / "card.json"
    export_sillytavern_card(card_data, st_path)
    assert st_path.exists()
    with open(st_path, "r", encoding="utf-8") as f:
        loaded_st = json.load(f)
    assert loaded_st["spec"] == "chara_card_v2"

    # 2. Standalone Lorebook
    lore_path = tmp_path / "lore.json"
    export_standalone_lorebook({"L0": []}, lore_path)
    assert lore_path.exists()

    # 3. AstrBot Persona
    astr_path = tmp_path / "astr.json"
    export_astrbot_persona(
        {"persona_id": "fc", "persona_name": "虚构", "system_prompt": "prompt", "begin_dialogs": []},
        astr_path,
    )
    assert astr_path.exists()

    # 4. Juus Brain format
    brain_path = tmp_path / "brain.json"
    export_juus_brain_format(card_data, raw, brain_path)
    assert brain_path.exists()
    with open(brain_path, "r", encoding="utf-8") as f:
        loaded_brain = json.load(f)
    assert loaded_brain["schema_version"] == "1.0"
    assert loaded_brain["character_id"] == "fictional_cruiser"
    assert loaded_brain["baseline_relationship"]["is_oath"] is True

