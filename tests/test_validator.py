"""Tests for QA validation rules: checking appellation, catchphrases, taboos, and baseline."""

from __future__ import annotations

from pipeline.extractor.models import CharacterRawMaterial
from pipeline.validator.reporter import CharacterValidator
from pipeline.validator.rules import (
    AppellationRule,
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

