"""Validator specifically for exported AstrBot persona files and directories."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from pipeline.validator.rules import AstrBotSchemaRule, RuleCheckResult


@dataclass
class AstrBotFileValidationResult:
    file_path: Path
    persona_id: str
    passed: bool
    results: List[RuleCheckResult] = field(default_factory=list)


def validate_astrbot_persona_dict(persona_data: Dict) -> RuleCheckResult:
    """Validate a single AstrBot persona dictionary."""
    rule = AstrBotSchemaRule()
    return rule.check(persona_data)


def validate_astrbot_file(file_path: Path) -> AstrBotFileValidationResult:
    """Validate a single AstrBot JSON file on disk."""
    rule = AstrBotSchemaRule()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        err = RuleCheckResult(
            rule_id=rule.RULE_ID,
            rule_name=rule.RULE_NAME,
            passed=False,
            severity="error",
            message=f"JSON 解析失败: {e}",
        )
        return AstrBotFileValidationResult(
            file_path=file_path,
            persona_id=file_path.stem,
            passed=False,
            results=[err],
        )

    res = rule.check(data)
    persona_id = data.get("persona_id", file_path.stem) if isinstance(data, dict) else file_path.stem
    return AstrBotFileValidationResult(
        file_path=file_path,
        persona_id=persona_id,
        passed=res.passed,
        results=[res],
    )


def validate_astrbot_dir(dir_path: Path) -> Tuple[int, int, List[AstrBotFileValidationResult]]:
    """Validate all *_astrbot.json files in a directory."""
    files = sorted(dir_path.glob("*_astrbot.json"))
    results = [validate_astrbot_file(f) for f in files]
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    return total, passed, results
