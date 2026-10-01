"""QA Reporter that evaluates rules and outputs structured validation reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from pipeline.extractor.models import CharacterRawMaterial
from pipeline.validator.rules import (
    AppellationRule,
    BaselineRule,
    CatchphraseRule,
    ConsistencyRule,
    RuleCheckResult,
    SchemaRule,
    TabooRule,
)


@dataclass
class CharacterQASummary:
    ship_group: int
    name_cn: str
    faction_cn: str
    passed: bool
    score: int  # 0 - 100
    results: List[RuleCheckResult] = field(default_factory=list)


@dataclass
class QAReport:
    generated_at: str
    total_characters: int
    passed_characters: int
    average_score: float
    character_summaries: List[CharacterQASummary] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# 角色卡自动质检报告（QA Report）",
            "",
            f"> 生成时间：{self.generated_at} ｜ 抽检总数：{self.total_characters} ｜ 合格数：{self.passed_characters} ｜ 平均得分：{self.average_score:.1f} / 100",
            "",
            "## 一、综合质检概览",
            "",
            "| ship_group | 角色名 | 阵营 | 质检状态 | 评分 | 核心检查项明细 |",
            "|---|---|---|---|---:|---|",
        ]
        for s in self.character_summaries:
            status_badge = "✅ PASS" if s.passed else "❌ FAIL"
            details_str = ", ".join([f"{r.rule_name}: {'✓' if r.passed else '✗'}" for r in s.results])
            lines.append(
                f"| {s.ship_group} | **{s.name_cn}** | {s.faction_cn} | {status_badge} | {s.score} | {details_str} |"
            )

        lines.extend([
            "",
            "## 二、逐项质检详情",
            "",
        ])
        for s in self.character_summaries:
            lines.append(f"### {s.name_cn}（ship_group: {s.ship_group}, {s.faction_cn}）- 得分: {s.score}")
            lines.append("")
            for r in s.results:
                icon = "✅" if r.passed else ("⚠️" if r.severity == "warning" else "❌")
                lines.append(f"- {icon} **{r.rule_name}**（`{r.rule_id}`）：{r.message}")
            lines.append("")

        return "\n".join(lines)


class CharacterValidator:
    """Executes all validation rules against character cards."""

    def __init__(self):
        self.rules = [
            SchemaRule(),
            AppellationRule(),
            TabooRule(),
            CatchphraseRule(),
            ConsistencyRule(),
            BaselineRule(),
        ]

    def validate_single(
        self, card_data: Dict, raw: CharacterRawMaterial
    ) -> CharacterQASummary:
        results: List[RuleCheckResult] = []
        errors = 0
        warnings = 0

        for r in self.rules:
            res = r.check(card_data, raw)
            results.append(res)
            if not res.passed:
                if res.severity == "error":
                    errors += 1
                else:
                    warnings += 1

        score = max(0, 100 - (errors * 20) - (warnings * 5))
        passed = errors == 0

        return CharacterQASummary(
            ship_group=raw.ship_group,
            name_cn=raw.name_cn,
            faction_cn=raw.faction_cn,
            passed=passed,
            score=score,
            results=results,
        )

    def validate_batch(
        self, cards: Dict[int, Dict], materials: Dict[int, CharacterRawMaterial]
    ) -> QAReport:
        summaries: List[CharacterQASummary] = []
        for sg, card in cards.items():
            raw = materials.get(sg)
            if raw:
                summary = self.validate_single(card, raw)
                summaries.append(summary)

        total = len(summaries)
        passed_cnt = sum(1 for s in summaries if s.passed)
        avg_score = (sum(s.score for s in summaries) / total) if total else 0.0

        return QAReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_characters=total,
            passed_characters=passed_cnt,
            average_score=avg_score,
            character_summaries=summaries,
        )

