"""Tests for QA validation rules: checking appellation, catchphrases, taboos, and baseline."""

from __future__ import annotations

from pipeline.extractor.models import CharacterRawMaterial
from pipeline.validator.reporter import CharacterValidator
from pipeline.validator.rules import (
    AppellationRule,
    AstrBotSchemaRule,
    BaselineRule,
    CatchphraseRule,
    ConsistencyRule,
    SchemaRule,
    TabooRule,
)


def make_sample_card(
    name="测试舰娘",
    system_prompt="你正在扮演测试舰娘。面对指挥官时要温柔体贴。",
    mes_example="{{user}}: 你好\n{{char}}: 指挥官，欢迎回来。",
    is_oath=True,
    affinity=200,
):
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": name,
            "description": "测试描述",
            "personality": "温和",
            "scenario": "母港日常",
            "first_mes": "指挥官，今天辛苦了。",
            "mes_example": mes_example,
            "system_prompt": system_prompt,
            "character_book": {"entries": [{"keys": ["测试"], "content": "条目"}]},
            "extensions": {
                "ship_group": 99999,
                "game_state": {"is_oath": is_oath, "affinity": affinity, "level": 125},
            },
        },
    }


def make_sample_raw():
    return CharacterRawMaterial(
        ship_group=99999,
        name_cn="测试舰娘",
        name_en="Test Ship",
        astrbot_id="test_ship",
        faction_key="eagle_union",
        faction_cn="白鹰",
    )


def test_appellation_rule_pass_and_fail():
    rule = AppellationRule()
    raw = make_sample_raw()

    # Pass
    card_pass = make_sample_card()
    res = rule.check(card_pass, raw)
    assert res.passed is True

    # Fail: using forbidden appellation
    card_forbidden = make_sample_card(system_prompt="主人，我来服务你了。")
    res_f = rule.check(card_forbidden, raw)
    assert res_f.passed is False
    assert "使用了违规称呼" in res_f.message


def test_taboo_rule_catches_ai_break():
    rule = TabooRule()
    raw = make_sample_raw()

    # Pass
    res = rule.check(make_sample_card(), raw)
    assert res.passed is True

    # Fail: AI assistant break
    card_break = make_sample_card(system_prompt="我是一个人工智能助手，请问有什么可以帮助您的？")
    res_b = rule.check(card_break, raw)
    assert res_b.passed is False
    assert "发现禁止使用的AI出戏词汇" in res_b.message


def test_baseline_rule_enforces_oath():
    rule = BaselineRule()
    raw = make_sample_raw()

    # Pass
    res = rule.check(make_sample_card(is_oath=True, affinity=200), raw)
    assert res.passed is True

    # Fail: not oath
    res_no_oath = rule.check(make_sample_card(is_oath=False, affinity=50), raw)
    assert res_no_oath.passed is False
    assert "必须为已誓约" in res_no_oath.message


def test_validator_batch_summary():
    validator = CharacterValidator()
    raw = make_sample_raw()
    card = make_sample_card()

    report = validator.validate_batch({99999: card}, {99999: raw})
    assert report.total_characters == 1
    assert report.passed_characters == 1
    assert report.average_score >= 95
    assert len(report.to_markdown()) > 100

def test_astrbot_schema_rule_valid_with_fictional_data():
    rule = AstrBotSchemaRule()
    valid_data = {
        "persona_id": "fictional_aurora",
        "system_prompt": "你正在扮演虚构舰娘极光。面对指挥官时要温柔体贴。",
        "begin_dialogs": [
            "指挥官：今天海上的巡逻报告已经整理出来了。",
            "（接过报告认真审视）辛苦了，指挥官。接下来的巡察就交给我吧，你先去喝杯茶休息一下。",
        ],
        "tools": None,
    }
    res = rule.check(valid_data)
    assert res.passed is True
    assert res.severity == "info"


def test_astrbot_schema_rule_rejects_persona_name():
    rule = AstrBotSchemaRule()
    invalid_data = {
        "persona_id": "fictional_aurora",
        "persona_name": "极光·守护者",  # Forbidden in AstrBot schema
        "system_prompt": "你正在扮演极光·守护者。",
        "begin_dialogs": ["指挥官：你好", "指挥官，我在。"],
        "tools": None,
    }
    res = rule.check(invalid_data)
    assert res.passed is False
    assert "persona_name" in res.message


def test_astrbot_schema_rule_rejects_dict_dialogs():
    rule = AstrBotSchemaRule()
    invalid_data = {
        "persona_id": "fictional_aurora",
        "system_prompt": "你正在扮演极光·守护者。",
        "begin_dialogs": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "我在"},
        ],
        "tools": None,
    }
    res = rule.check(invalid_data)
    assert res.passed is False
    assert "必须为字符串类型" in res.message


def test_astrbot_schema_rule_rejects_odd_dialogs():
    rule = AstrBotSchemaRule()
    invalid_data = {
        "persona_id": "fictional_aurora",
        "system_prompt": "你正在扮演极光·守护者。",
        "begin_dialogs": ["指挥官：你好"],  # Odd count (1)
        "tools": None,
    }
    res = rule.check(invalid_data)
    assert res.passed is False
    assert "偶数" in res.message


def test_astrbot_schema_rule_allows_empty_tools_list():
    rule = AstrBotSchemaRule()
    data = {
        "persona_id": "fictional_aurora",
        "system_prompt": "你正在扮演极光·守护者。",
        "begin_dialogs": ["指挥官：你好", "我在。"],
        "tools": [],  # Explicit empty tools list to disable tools
    }
    res = rule.check(data)
    assert res.passed is True


def test_appellation_rule_with_custom_appellation():
    rule = AppellationRule()
    raw = make_sample_raw()
    raw.appellation_user = "测试称呼"

    # Pass: card uses custom appellation
    card_pass = make_sample_card(
        system_prompt="你正在扮演测试舰娘。面对测试称呼时要温柔体贴。始终以‘测试称呼’称呼对方。",
        mes_example="{{user}}: 你好\n{{char}}: 测试称呼，欢迎回来。",
    )
    card_pass["data"]["first_mes"] = "测试称呼，今天辛苦了。"
    card_pass["data"]["post_history_instructions"] = "坚决以‘测试称呼’或{{user}}称呼对方"
    res_pass = rule.check(card_pass, raw)
    assert res_pass.passed is True

    # Fail: card hardcodes 指挥官
    card_hardcoded = make_sample_card(
        system_prompt="你正在扮演测试舰娘。面对指挥官时要温柔体贴。始终以‘指挥官’称呼对方。",
        mes_example="{{user}}: 你好\n{{char}}: 指挥官，欢迎回来。",
    )
    card_hardcoded["data"]["first_mes"] = "指挥官，今天辛苦了。"
    card_hardcoded["data"]["post_history_instructions"] = "坚决以‘指挥官’或{{user}}称呼对方"
    res_fail = rule.check(card_hardcoded, raw)
    assert res_fail.passed is False
    assert "未检测到对‘测试称呼’的标准称呼" in res_fail.message or "写死‘指挥官’称呼" in res_fail.message


def test_appellation_rule_with_generated_card():
    from pipeline.generator.builder import PersonaBuilder

    raw = make_sample_raw()
    raw.appellation_user = "测试称呼"
    builder = PersonaBuilder()
    card = builder.build_sillytavern_v2(raw)

    rule = AppellationRule()
    res = rule.check(card, raw)
    assert res.passed is True

