"""Tests for SillyTavern V2 and Lorebook generation using FICTIONAL character data."""

from __future__ import annotations

from pipeline.extractor.models import (
    CharacterRawMaterial,
    ChatLine,
    JUUsChatTopic,
    VoiceLine,
)
from pipeline.generator.builder import PersonaBuilder
from pipeline.generator.lorebook import assemble_three_layer_lorebook


def create_fictional_character() -> CharacterRawMaterial:
    return CharacterRawMaterial(
        ship_group=77777,
        name_cn="极光·守护者",
        name_en="Aurora Guardian",
        astrbot_id="aurora",
        faction_key="eagle_union",
        faction_cn="白鹰",
        ship_type="战列舰",
        cv="虚构CV",
        skin_ids=["777770"],
        chat_topics=[
            JUUsChatTopic(
                topic_id=1,
                name="极光测试",
                unlock_desc="誓约解锁",
                lines=[
                    ChatLine(id=1, sender_group=77777, is_commander=False, text="指挥官，极光升起来了。"),
                    ChatLine(id=2, sender_group=0, is_commander=True, text="真美啊。"),
                ],
            )
        ],
        voicelines=[
            VoiceLine(skin_id="777770", voicekey="login", text="指挥官，今天也要保持元气。"),
            VoiceLine(skin_id="777770", voicekey="feeling5", text="愿与你守护彼此直到永恒。", is_oath_or_ex=True),
        ],
    )


def test_assemble_three_layer_lorebook():
    raw = create_fictional_character()
    lore = assemble_three_layer_lorebook(raw)

    assert "L0_port" in lore
    assert "L1_faction" in lore
    assert "L2_character" in lore
    assert len(lore["L0_port"]) >= 3
    assert len(lore["L2_character"]) >= 4


def test_build_sillytavern_v2():
    raw = create_fictional_character()
    builder = PersonaBuilder()
    card = builder.build_sillytavern_v2(raw)

    assert card["spec"] == "chara_card_v2"
    assert card["spec_version"] == "2.0"
    data = card["data"]
    assert data["name"] == "极光·守护者"
    assert "{{user}}" in data["scenario"]
    assert "{user}" not in data["scenario"].replace("{{user}}", "")
    assert "指挥官" in data["system_prompt"]
    assert "character_book" in data
    assert data["character_book"]["entries"]

    ext = data["extensions"]
    assert ext["ship_group"] == 77777
    assert ext["game_state"]["is_oath"] is True
    assert ext["game_state"]["affinity"] == 200


def test_build_astrbot_persona():
    raw = create_fictional_character()
    builder = PersonaBuilder()
    astr = builder.build_astrbot_persona(raw)

    assert astr["persona_id"] == "aurora"
    assert "persona_name" not in astr
    assert "指挥官" in astr["system_prompt"]
    assert len(astr["begin_dialogs"]) >= 2
    assert len(astr["begin_dialogs"]) % 2 == 0
    assert isinstance(astr["begin_dialogs"][0], str)
    assert astr["tools"] is None


def test_build_card_scenario_user_macro_and_custom_appellation():
    raw = create_fictional_character()
    raw.appellation_user = "测试称呼"
    builder = PersonaBuilder()
    card = builder.build_sillytavern_v2(raw)
    data = card["data"]

    assert "{{user}}" in data["scenario"]
    assert "{user}" not in data["scenario"].replace("{{user}}", "")
    assert "测试称呼" in data["scenario"]

    sys_prompt = data["system_prompt"]
    post_history = data["post_history_instructions"]

    assert "始终以‘指挥官’称呼" not in sys_prompt
    assert "坚决以‘指挥官’" not in post_history
    assert "始终以‘测试称呼’称呼" in sys_prompt
    assert "坚决以‘测试称呼’或{{user}}称呼对方" in post_history

