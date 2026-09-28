"""Tests for batch-mode ship registry, resume logic, and L0/L1 export (FICTIONAL data)."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.cli import export_l0_l1_lorebooks, is_exported, resolve_targets
from pipeline.config import PLAYABLE_NATIONALITIES, build_ship_registry, slugify_astrbot_id
from pipeline.extractor.aggregator import RawDataAggregator


def _write_stats(path: Path, entries: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)


def _fictional_tables(tmp_path: Path):
    cn = tmp_path / "CN" / "sharecfgdata" / "ship_data_statistics.json"
    en = tmp_path / "EN" / "sharecfgdata" / "ship_data_statistics.json"
    _write_stats(
        cn,
        {
            # normal ship, two stat rows -> dedupe to one group
            "777771": {"id": 777771, "name": "虚构测试舰", "english_name": "Test Ship",
                       "nationality": 1, "type": 2},
            "777772": {"id": 777772, "name": "虚构测试舰", "english_name": "Test Ship",
                       "nationality": 1, "type": 2},
            # META ship stays independent
            "977771": {"id": 977771, "name": "虚构测试舰·META", "english_name": "Test Ship.META",
                       "nationality": 97, "type": 2},
            # bulin (98) excluded
            "988881": {"id": 988881, "name": "试作型布里MKII", "english_name": "Prototype Bulin MKII",
                       "nationality": 98, "type": 1},
        },
    )
    _write_stats(
        en,
        {
            # EN-only new ship -> fallback_en
            "777881": {"id": 777881, "name": "Fictional New Ship", "english_name": "New Ship",
                       "nationality": 3, "type": 5},
            # CN wins over EN for the same group
            "777773": {"id": 777773, "name": "EN Override", "english_name": "Override",
                       "nationality": 1, "type": 2},
        },
    )
    return cn, en


def test_build_ship_registry_fictional(tmp_path: Path):
    cn, en = _fictional_tables(tmp_path)
    reg = build_ship_registry(cn, en)

    assert 77777 in reg and 97777 in reg and 77788 in reg
    assert 98888 not in reg  # bulin excluded
    assert reg[77777].name_cn == "虚构测试舰"  # CN wins, deduped
    assert not reg[77777].fallback_en
    assert reg[77788].fallback_en  # EN-only group flagged
    assert "[pending_cn_supplement]" in reg[77788].notes
    assert reg[97777].faction_key == "meta_faction"  # META independent
    # astrbot ids are deterministic ASCII slugs
    assert reg[77777].astrbot_id == "test_ship"
    assert reg[97777].astrbot_id == "test_ship_meta"


def test_slugify_collision_suffix():
    # same english name, different groups -> second gets group suffix
    assert slugify_astrbot_id("Test Ship", 77777) == "test_ship"


def test_resolve_targets_faction_and_limit(tmp_path: Path):
    cn, en = _fictional_tables(tmp_path)
    raw_dir = tmp_path
    # write minimal words tables so aggregator can load (not needed for resolve)
    all_targets = resolve_targets(raw_dir, batch=True)
    assert set(all_targets) == {77777, 97777, 77788}

    eagle = resolve_targets(raw_dir, batch=True, faction="eagle_union")
    assert set(eagle) == {77777}

    limited = resolve_targets(raw_dir, batch=True, limit=2)
    assert len(limited) == 2
    assert list(limited) == sorted(limited)  # deterministic order

    pilot = resolve_targets(raw_dir, batch=False)
    assert len(pilot) == 8  # BATCH_1_SHIPS preserved as pilot subset


def test_is_exported_resume(tmp_path: Path):
    out = tmp_path / "output"
    assert not is_exported(out, "test_ship")
    for sub in ["sillytavern", "lorebook", "astrbot", "juus_brain"]:
        d = out / sub
        d.mkdir(parents=True, exist_ok=True)
    (out / "sillytavern" / "test_ship_sillytavern_v2.json").write_text("{}")
    (out / "lorebook" / "test_ship_lorebook.json").write_text("{}")
    (out / "astrbot" / "test_ship_astrbot.json").write_text("{}")
    assert not is_exported(out, "test_ship")  # missing one file
    (out / "juus_brain" / "test_ship_juus_brain.json").write_text("{}")
    assert is_exported(out, "test_ship")


def test_export_l0_l1_lorebooks(tmp_path: Path):
    out = tmp_path / "output"
    written = export_l0_l1_lorebooks(out, ["eagle_union", "meta_faction", "dragon_empery"])
    names = {p.name for p in written}
    assert "L0_port_common.json" in names
    assert "L1_eagle_union.json" in names
    assert "L1_meta_faction.json" in names
    assert "L1_dragon_empery.json" in names
    l0 = json.loads((out / "lorebook" / "L0_port_common.json").read_text(encoding="utf-8"))
    assert l0["layer"] == "L0_port" and len(l0["entries"]) == 4


def test_extract_batch_with_targets_param(tmp_path: Path):
    from tests.test_extractor import setup_fictional_raw_tables

    setup_fictional_raw_tables(tmp_path)
    agg = RawDataAggregator(raw_dir=tmp_path)
    # fictional registry overriding BATCH_1_SHIPS
    from pipeline.config import ShipTargetConfig

    targets = {
        88888: ShipTargetConfig(
            ship_group=88888, id="star_voyager", name_cn="试航者·星穹",
            name_en="Star Voyager", astrbot_id="star_voyager",
            faction_key="eagle_union", faction_cn="白鹰",
        )
    }
    mats = agg.extract_batch([88888], targets=targets)
    assert 88888 in mats
    assert mats[88888].astrbot_id == "star_voyager"
    assert mats[88888].faction_key == "eagle_union"


def _maid_like_material():
    """Fictional maid character whose official voicelines use 主人 (all fictional)."""
    from pipeline.extractor.models import (
        CharacterRawMaterial, VoiceLine,
    )

    return CharacterRawMaterial(
        ship_group=77777,
        name_cn="虚构女仆",
        name_en="Fictional Maid",
        astrbot_id="fictional_maid",
        faction_key="royal_navy",
        faction_cn="皇家",
        ship_type="轻巡洋舰",
        voicelines=[
            VoiceLine(skin_id="0", voicekey="login", text="主人，欢迎回来，今天也要好好休息哦。"),
            VoiceLine(skin_id="0", voicekey="main1", text="能侍奉主人，是咱的荣幸。"),
        ],
        chat_topics=[],
    )


def _card_with_mes_example(mes_example: str) -> dict:
    return {
        "data": {
            "system_prompt": "你是虚构女仆，称呼其为'指挥官'或{{user}}。",
            "mes_example": mes_example,
            "first_mes": "主人，欢迎回来。",
            "description": "虚构角色",
            "personality": "温柔",
            "scenario": "",
            "alternate_greetings": [],
            "tags": ["虚构"],
        }
    }


def test_appellation_rule_allows_canonical_master_address():
    """Official 主人 address (maid archetype) -> warning, not failure."""
    from pipeline.validator.rules import AppellationRule

    raw = _maid_like_material()
    card = _card_with_mes_example("<START>\n{char}: 主人，茶已经泡好了。")
    res = AppellationRule().check(card, raw)
    assert res.passed is True
    assert res.severity == "warning"


def test_appellation_rule_still_fails_master_without_canonical_source():
    """主人 in dialogue but absent from official voicelines -> error."""
    from pipeline.validator.rules import AppellationRule

    raw = _maid_like_material()
    # rewrite voicelines without 主人
    from pipeline.extractor.models import VoiceLine
    raw.voicelines = [VoiceLine(skin_id="0", voicekey="login", text="指挥官，欢迎回来。")]
    card = _card_with_mes_example("<START>\n{char}: 主人，茶已经泡好了。")
    res = AppellationRule().check(card, raw)
    assert res.passed is False
    assert res.severity == "error"


def test_appellation_rule_still_fails_player_appellation():
    """玩家/用户 remain hard errors even with canonical 主人."""
    from pipeline.validator.rules import AppellationRule

    raw = _maid_like_material()
    card = _card_with_mes_example("<START>\n{char}: 玩家你好。")
    res = AppellationRule().check(card, raw)
    assert res.passed is False
    assert res.severity == "error"
