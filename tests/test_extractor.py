"""Tests for raw data aggregator and variant merging using FICTIONAL character data."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.extractor.aggregator import RawDataAggregator
from pipeline.extractor.models import (
    CharacterRawMaterial,
    ChatLine,
    JUUsChatTopic,
    VoiceLine,
)
from pipeline.extractor.rules import merge_variants


def setup_fictional_raw_tables(raw_dir: Path):
    """Setup mock raw directory with 100% fictional ship data."""
    cn_sharecfg = raw_dir / "CN" / "ShareCfg"
    cn_sharecfgdata = raw_dir / "CN" / "sharecfgdata"
    cn_sharecfg.mkdir(parents=True, exist_ok=True)
    cn_sharecfgdata.mkdir(parents=True, exist_ok=True)

    # Fictional ship group 88888: "星穹·试航者号" (Fictional Star Voyager)
    # ship id = 888881 (888881 // 10 == 88888)
    stats_data = {
        "888881": {
            "id": 888881,
            "name": "试航者·星穹",
            "english_name": "Star Voyager",
            "nationality": 1,
            "type": 5,
            "skin_id": 888880,
        }
    }
    with open(cn_sharecfgdata / "ship_data_statistics.json", "w", encoding="utf-8") as f:
        json.dump(stats_data, f)

    words_data = {
        "888880": {
            "login": "指挥官，星穹号准备就绪。",
            "feeling5": "在群星的见证下，我与你的誓约永不褪色。",
            "propose": "和我一起航向未知的深空吧，我的指挥官。",
            "main": "恒星的光辉穿透夜空。|别逞强，累了就靠在我肩上休息。",
        }
    }
    with open(cn_sharecfgdata / "ship_skin_words.json", "w", encoding="utf-8") as f:
        json.dump(words_data, f)

    words_extra_data = {
        "888880": {
            "feeling5": [[1100, "只要你在我身边，整个宇宙都变得温柔起来。"]],
            "login": [[1100, "欢迎回到星穹舰桥，指挥官。文件我已经帮你整理好了。"]],
        }
    }
    with open(cn_sharecfg / "ship_skin_words_extra.json", "w", encoding="utf-8") as f:
        json.dump(words_extra_data, f)

    chat_group_data = {
        "101": {
            "id": 101,
            "name": "星海观测计划",
            "ship_group": 88888,
            "unlock_desc": "获得角色",
            "content": [1001, 1002],
        }
    }
    with open(cn_sharecfg / "activity_ins_chat_group.json", "w", encoding="utf-8") as f:
        json.dump(chat_group_data, f)

    chat_lang_data = {
        "1001": {
            "id": 1001,
            "ship_group": 88888,
            "param": "指挥官，今晚的星空非常澄澈呢。",
            "option": "",
        },
        "1002": {
            "id": 1002,
            "ship_group": 0,
            "param": "要一起去观星台看看吗？",
            "option": "",
        },
    }
    with open(cn_sharecfg / "activity_ins_chat_language.json", "w", encoding="utf-8") as f:
        json.dump(chat_lang_data, f)

    # Empty optional tables
    for tbl in [
        "activity_ins_template.json",
        "activity_ins_language.json",
        "activity_ins_npc_template.json",
        "memory_template.json",
    ]:
        with open(cn_sharecfg / tbl, "w", encoding="utf-8") as f:
            json.dump({}, f)


def test_fictional_extraction(tmp_path: Path):
    setup_fictional_raw_tables(tmp_path)
    aggregator = RawDataAggregator(raw_dir=tmp_path)
    mat = aggregator.extract_single(ship_group=88888)

    assert mat.name_cn == "试航者·星穹"
    assert mat.name_en == "Star Voyager"
    assert len(mat.chat_topics) == 1
    assert mat.chat_topics[0].name == "星海观测计划"
    assert len(mat.chat_topics[0].lines) == 2
    assert any("群星" in v.text for v in mat.voicelines)
    assert mat.stats.chat_topics_count == 1
    assert mat.stats.total_voicelines_count > 0


def test_variant_merging():
    canonical = CharacterRawMaterial(
        ship_group=88888,
        name_cn="试航者·基础型",
        name_en="Voyager Base",
        astrbot_id="voyager",
        faction_key="fictional",
        faction_cn="虚构",
        voicelines=[VoiceLine(skin_id="888880", voicekey="login", text="基础型报到")],
    )
    variant = CharacterRawMaterial(
        ship_group=88889,
        name_cn="试航者·觉醒型",
        name_en="Voyager II",
        astrbot_id="voyager_ii",
        faction_key="fictional",
        faction_cn="虚构",
        voicelines=[VoiceLine(skin_id="888890", voicekey="login", text="觉醒型出击")],
    )

    merged = merge_variants(canonical, [variant])
    assert len(merged.voicelines) == 2
    assert 88889 in merged.merged_groups
    assert any("觉醒型" in n for n in merged.notes)


def test_exact_skin_matching_behavior():
    """Exact skin matching skin_id[:-1] == group vs legacy prefix (Issue #27)."""
    # Exact match: group 88888, skin 888880
    assert RawDataAggregator.is_skin_match("888880", "88888") is True
    assert RawDataAggregator.is_skin_match("888881", "88888") is True
    # Prefix collision scenario: group 888 vs skin 888880
    # Legacy prefix matching returns True (false positive collision!)
    assert RawDataAggregator.is_skin_match_legacy("888880", "888") is True
    # Exact matching prevents prefix collision
    assert RawDataAggregator.is_skin_match("888880", "888") is False


def test_compare_skin_matching_detects_collision(tmp_path: Path):
    """compare_skin_matching detects discrepancies when prefix-collision skins exist."""
    cn_sharecfg = tmp_path / "CN" / "ShareCfg"
    cn_sharecfgdata = tmp_path / "CN" / "sharecfgdata"
    cn_sharecfg.mkdir(parents=True, exist_ok=True)
    cn_sharecfgdata.mkdir(parents=True, exist_ok=True)

    # Fictional table with group 888 and colliding skin 88810
    with open(cn_sharecfgdata / "ship_skin_words.json", "w", encoding="utf-8") as f:
        json.dump({"88810": {"login": "test"}}, f)
    with open(cn_sharecfgdata / "ship_data_statistics.json", "w", encoding="utf-8") as f:
        json.dump({}, f)
    with open(cn_sharecfg / "ship_skin_words_extra.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

    aggregator = RawDataAggregator(raw_dir=tmp_path)
    # Check group 888: 88810 has len 5, 88810[:-1] is 8881 != 888
    diffs = aggregator.compare_skin_matching(ship_groups=[888])
    assert len(diffs) == 1
    assert diffs[0]["ship_group"] == 888
    assert "88810" in diffs[0]["prefix_only"]
    assert diffs[0]["exact_only"] == []


def test_extract_single_does_not_swallow_colliding_skin(tmp_path: Path):
    """Regression for Issue #27 / PR #32 F-3: extract_single() and the
    skin_ids list are the two production paths that actually changed when
    skin matching moved from ``startswith`` to exact ``skin_id[:-1] ==
    ship_group``. The helper-level tests above don't exercise either path,
    so this test constructs a short group (888) with a colliding skin id
    (88810, which actually belongs to group 8881) and asserts group 888's
    extraction never absorbs it. On the old startswith-based production
    code, this test fails: 88810 starts with "888", so its voicelines and
    skin id would incorrectly leak into group 888's material.
    """
    cn_sharecfg = tmp_path / "CN" / "ShareCfg"
    cn_sharecfgdata = tmp_path / "CN" / "sharecfgdata"
    cn_sharecfg.mkdir(parents=True, exist_ok=True)
    cn_sharecfgdata.mkdir(parents=True, exist_ok=True)

    # Fictional group 888 (ship id 8880, 8880 // 10 == 888) and a colliding
    # skin "88810" that actually belongs to a different group (8881).
    stats_data = {
        "8880": {
            "id": 8880,
            "name": "测试·舰888",
            "english_name": "Test Ship 888",
            "nationality": 1,
            "type": 1,
        }
    }
    with open(cn_sharecfgdata / "ship_data_statistics.json", "w", encoding="utf-8") as f:
        json.dump(stats_data, f)

    words_data = {
        "8880": {"login": "虚构·888号舰娘报到。"},
        "88810": {"login": "COLLISION_SHOULD_NOT_LEAK_INTO_888"},
    }
    with open(cn_sharecfgdata / "ship_skin_words.json", "w", encoding="utf-8") as f:
        json.dump(words_data, f)
    with open(cn_sharecfg / "ship_skin_words_extra.json", "w", encoding="utf-8") as f:
        json.dump({}, f)
    for tbl in [
        "activity_ins_chat_group.json",
        "activity_ins_chat_language.json",
        "activity_ins_template.json",
        "activity_ins_language.json",
        "activity_ins_npc_template.json",
        "memory_template.json",
    ]:
        with open(cn_sharecfg / tbl, "w", encoding="utf-8") as f:
            json.dump({}, f)

    aggregator = RawDataAggregator(raw_dir=tmp_path)
    mat = aggregator.extract_single(ship_group=888)

    assert "88810" not in mat.skin_ids
    assert "8880" in mat.skin_ids
    assert all(v.skin_id != "88810" for v in mat.voicelines)
    assert all("COLLISION" not in v.text for v in mat.voicelines)
    assert any("888号舰娘报到" in v.text for v in mat.voicelines)
