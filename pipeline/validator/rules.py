"""Validation rules for checking appellation, catchphrases, taboos, and consistency."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pipeline.extractor.models import CharacterRawMaterial


@dataclass
class RuleCheckResult:
    rule_id: str
    rule_name: str
    passed: bool
    severity: str  # "error" or "warning"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


FORBIDDEN_AI_TABOOS = [
    "作为AI",
    "作为人工智能",
    "人工智能助手",
    "语言模型",
    "大语言模型",
    "我只是一个程序",
    "无法提供主观",
    "作为计算机程序",
    "知识库",
    "AI助手",
]

CHARACTER_CATCHPHRASE_MAP: Dict[int, List[str]] = {
    40503: ["别逞强", "担心", "毒药", "黑胶", "音乐", "文件"],
    30510: ["呵呵", "武藏", "依靠", "茶", "水可载舟", "安心"],
    49902: ["我的孩子", "乐章", "交响", "慈爱", "奏响"],
    10702: ["蓝色幽灵", "助力", "歌谣", "曲风", "列克星敦"],
    10705: ["海风", "温柔", "守护", "约克城", "陪伴"],
    20516: ["狮", "红茶", "威仪", "掌控", "王权"],
    970201: ["SG雷达", "信标", "守护", "微光", "执念"],
    20238: ["虎", "英气", "忠诚", "巡逻", "冲锋"],
}


class AppellationRule:
    """Checks that the character addresses the user as 指挥官 or {{user}}."""

    RULE_ID = "RULE_APPELLATION"
    RULE_NAME = "称呼规范检查"

    def check(self, card_data: Dict, raw: CharacterRawMaterial) -> RuleCheckResult:
        data = card_data.get("data", {})
        sys_prompt = data.get("system_prompt", "")
        mes_example = data.get("mes_example", "")
        first_mes = data.get("first_mes", "")

        has_commander = "指挥官" in sys_prompt or "指挥官" in mes_example or "指挥官" in first_mes
        has_user_var = "{{user}}" in sys_prompt or "{{user}}" in mes_example or "{{user}}" in first_mes

        forbidden_appellations = ["主人", "玩家", "用户", "亲爱的用户"]
        found_forbidden = [
            fa for fa in forbidden_appellations
            if fa in sys_prompt or fa in mes_example
        ]

        if found_forbidden:
            # Canonical-address exemption (batch mode): if the character's own
            # official voicelines use 主人 (e.g. Royal Navy maid ships), it is
            # their authentic form of address, not a generation defect.
            # Downgrade to a warning instead of failing.
            only_master = found_forbidden == ["主人"]
            canonical_master = any("主人" in v.text for v in raw.voicelines)
            if only_master and canonical_master:
                return RuleCheckResult(
                    rule_id=self.RULE_ID,
                    rule_name=self.RULE_NAME,
                    passed=True,
                    severity="warning",
                    message="角色官方语音本身以'主人'称呼指挥官（如皇家女仆队），视为角色固有称呼，予以放行",
                    details={"found": found_forbidden, "canonical": True},
                )
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message=f"使用了违规称呼: {found_forbidden}",
                details={"found": found_forbidden},
            )

        if not (has_commander or has_user_var):
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message="未检测到对‘指挥官’或{{user}}的标准称呼",
                details={},
            )

        return RuleCheckResult(
            rule_id=self.RULE_ID,
            rule_name=self.RULE_NAME,
            passed=True,
            severity="info",
            message="称呼规范检查通过，正确锚定‘指挥官’/{{user}}",
            details={},
        )


class TabooRule:
    """Checks for prohibited AI assistant breaks and out-of-character taboos."""

    RULE_ID = "RULE_TABOO"
    RULE_NAME = "禁忌词与出戏检查"

    def check(self, card_data: Dict, raw: CharacterRawMaterial) -> RuleCheckResult:
        data = card_data.get("data", {})
        text_corpus = (
            data.get("system_prompt", "")
            + " "
            + data.get("description", "")
            + " "
            + data.get("first_mes", "")
            + " "
            + data.get("mes_example", "")
        )

        found_taboos = [t for t in FORBIDDEN_AI_TABOOS if t in text_corpus]
        if found_taboos:
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message=f"发现禁止使用的AI出戏词汇: {found_taboos}",
                details={"taboos": found_taboos},
            )

        return RuleCheckResult(
            rule_id=self.RULE_ID,
            rule_name=self.RULE_NAME,
            passed=True,
            severity="info",
            message="禁忌词检查通过，未发现AI破坏沉浸感词汇",
            details={},
        )


class CatchphraseRule:
    """Checks that character core catchphrases and tone markers are present."""

    RULE_ID = "RULE_CATCHPHRASE"
    RULE_NAME = "口癖与语气特征检查"

    def check(self, card_data: Dict, raw: CharacterRawMaterial) -> RuleCheckResult:
        data = card_data.get("data", {})
        text_corpus = (
            data.get("system_prompt", "")
            + " "
            + data.get("personality", "")
            + " "
            + data.get("description", "")
            + " "
            + data.get("first_mes", "")
            + " "
            + data.get("mes_example", "")
        )

        expected = CHARACTER_CATCHPHRASE_MAP.get(raw.ship_group, [raw.name_cn])
        matched = [e for e in expected if e in text_corpus]

        if not matched:
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="warning",
                message=f"未充分匹配到该角色的预期口癖/特征词（期望: {expected}）",
                details={"expected": expected, "matched": matched},
            )

        coverage_ratio = len(matched) / len(expected)
        return RuleCheckResult(
            rule_id=self.RULE_ID,
            rule_name=self.RULE_NAME,
            passed=True,
            severity="info",
            message=f"口癖特征检查通过 (覆盖率: {coverage_ratio:.0%}, 匹配: {matched})",
            details={"matched": matched, "ratio": coverage_ratio},
        )


class ConsistencyRule:
    """Checks consistency with raw data (name, group, faction, baseline)."""

    RULE_ID = "RULE_CONSISTENCY"
    RULE_NAME = "原始素材一致性检查"

    def check(self, card_data: Dict, raw: CharacterRawMaterial) -> RuleCheckResult:
        data = card_data.get("data", {})
        name = data.get("name", "")
        ext = data.get("extensions", {})
        sg = ext.get("ship_group")

        if name != raw.name_cn:
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message=f"角色名与原始数据不一致: 卡片='{name}', 原始='{raw.name_cn}'",
                details={},
            )

        if sg != raw.ship_group:
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message=f"ship_group 不匹配: 卡片={sg}, 原始={raw.ship_group}",
                details={},
            )

        return RuleCheckResult(
            rule_id=self.RULE_ID,
            rule_name=self.RULE_NAME,
            passed=True,
            severity="info",
            message="原始素材一致性检查通过",
            details={},
        )


class BaselineRule:
    """Checks baseline oath and affinity 200 state in game_state and card."""

    RULE_ID = "RULE_BASELINE"
    RULE_NAME = "誓约与关系基线检查"

    def check(self, card_data: Dict, raw: CharacterRawMaterial) -> RuleCheckResult:
        data = card_data.get("data", {})
        ext = data.get("extensions", {})
        gs = ext.get("game_state", {})

        is_oath = gs.get("is_oath") is True
        affinity = gs.get("affinity", 0)
        level = gs.get("level", 0)

        if not is_oath or affinity < 200:
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message=f"关系基线不合规: 必须为已誓约且好感度200 (当前: is_oath={is_oath}, affinity={affinity})",
                details=gs,
            )

        return RuleCheckResult(
            rule_id=self.RULE_ID,
            rule_name=self.RULE_NAME,
            passed=True,
            severity="info",
            message=f"誓约基线合规 (已誓约, 好感={affinity}, 等级={level})",
            details=gs,
        )


class SchemaRule:
    """Checks SillyTavern V2 spec schema conformance."""

    RULE_ID = "RULE_SCHEMA"
    RULE_NAME = "SillyTavern V2 规范检查"

    def check(self, card_data: Dict, raw: CharacterRawMaterial) -> RuleCheckResult:
        if card_data.get("spec") != "chara_card_v2" or card_data.get("spec_version") != "2.0":
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message="卡片 spec 不符合 chara_card_v2 2.0 规范",
                details={},
            )

        data = card_data.get("data", {})
        required_keys = [
            "name",
            "description",
            "personality",
            "scenario",
            "first_mes",
            "mes_example",
            "system_prompt",
            "character_book",
        ]
        missing = [k for k in required_keys if not data.get(k)]
        if missing:
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="error",
                message=f"缺少必须的卡片字段: {missing}",
                details={"missing": missing},
            )

        char_book = data.get("character_book", {})
        entries = char_book.get("entries", [])
        if not entries:
            return RuleCheckResult(
                rule_id=self.RULE_ID,
                rule_name=self.RULE_NAME,
                passed=False,
                severity="warning",
                message="未发现内置角色专属世界书条目 (character_book.entries 为空)",
                details={},
            )

        return RuleCheckResult(
            rule_id=self.RULE_ID,
            rule_name=self.RULE_NAME,
            passed=True,
            severity="info",
            message=f"SillyTavern V2 格式校验通过 (内置专属世界书: {len(entries)} 条)",
            details={"entries_count": len(entries)},
        )

