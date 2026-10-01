"""Command-line interface for the Juus Companion Persona Pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from pipeline.config import (
    BATCH_1_SHIPS,
    DEFAULT_DATA_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RAW_DIR,
    ShipTargetConfig,
    build_ship_registry,
)
from pipeline.exporter.astrbot import export_astrbot_persona, export_astrbot_persona_names
from pipeline.exporter.brain import export_juus_brain_format
from pipeline.exporter.sillytavern import export_sillytavern_card, export_standalone_lorebook
from pipeline.extractor.aggregator import RawDataAggregator
from pipeline.extractor.models import CharacterRawMaterial
from pipeline.fetcher.client import Fetcher
from pipeline.generator.builder import PersonaBuilder
from pipeline.generator.llm_client import LLMClient
from pipeline.generator.lorebook import assemble_three_layer_lorebook
from pipeline.validator.reporter import CharacterValidator, QAReport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")


def is_exported(output_dir: Path, astrbot_id: str) -> bool:
    """Resume check: all four export formats already generated for this persona."""
    expected = [
        output_dir / "sillytavern" / f"{astrbot_id}_sillytavern_v2.json",
        output_dir / "lorebook" / f"{astrbot_id}_lorebook.json",
        output_dir / "astrbot" / f"{astrbot_id}_astrbot.json",
        output_dir / "juus_brain" / f"{astrbot_id}_juus_brain.json",
    ]
    return all(p.exists() for p in expected)


def export_l0_l1_lorebooks(output_dir: Path, faction_keys: List[str]) -> List[Path]:
    """Export L0 port-common and per-faction L1 lorebooks (generated once per run)."""
    from dataclasses import asdict

    from pipeline.generator.lorebook import L0_PORT_ENTRIES, L1_FACTION_ENTRIES

    lore_dir = output_dir / "lorebook"
    lore_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    l0_path = lore_dir / "L0_port_common.json"
    export_standalone_lorebook(
        {"layer": "L0_port", "entries": [asdict(e) for e in L0_PORT_ENTRIES]},
        l0_path,
    )
    written.append(l0_path)

    for fk in sorted(set(faction_keys)):
        entries = L1_FACTION_ENTRIES.get(fk, [])
        if not entries:
            logger.warning("No L1 lorebook entries defined for faction '%s'", fk)
            continue
        p = lore_dir / f"L1_{fk}.json"
        export_standalone_lorebook(
            {"layer": f"L1_{fk}", "entries": [asdict(e) for e in entries]}, p
        )
        written.append(p)
    return written


def resolve_targets(
    raw_dir: Path,
    batch: bool = False,
    limit: Optional[int] = None,
    faction: Optional[str] = None,
    groups: Optional[List[int]] = None,
) -> Dict[int, ShipTargetConfig]:
    """Resolve the ship target registry for this run.

    - No flags and no groups -> hardcoded BATCH_1_SHIPS pilot list.
    - --groups -> those groups resolved from the full registry (hand-written
      BATCH_1 configs take precedence for the original 8 ships).
    - --batch -> full list-driven registry from ship_data_statistics
      (CN primary, EN fallback), optionally filtered by faction
      and capped by limit (deterministic: sorted by ship_group).
    """
    if not batch and not groups:
        return dict(BATCH_1_SHIPS)
    registry = build_ship_registry(
        raw_dir / "CN/sharecfgdata/ship_data_statistics.json",
        raw_dir / "EN/sharecfgdata/ship_data_statistics.json",
    )
    # Hand-written BATCH_1 configs (notes, astrbot_id, merges) take precedence.
    for g, cfg in BATCH_1_SHIPS.items():
        if g in registry:
            registry[g] = cfg
    if groups is not None:
        # Explicit group list: keep registry entries; unknown groups are left
        # out and derived from raw stats at extraction time (legacy behavior).
        return {g: registry[g] for g in groups if g in registry}
    if faction:
        registry = {g: c for g, c in registry.items() if c.faction_key == faction}
    items = sorted(registry.items())
    if limit is not None:
        items = items[:limit]
    return dict(items)


def run_pipeline(
    raw_dir: Path = DEFAULT_RAW_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    groups: Optional[List[int]] = None,
    force_fetch: bool = False,
    offline: bool = False,
    batch: bool = False,
    limit: Optional[int] = None,
    faction: Optional[str] = None,
    resume: bool = False,
    targets: Optional[Dict[int, ShipTargetConfig]] = None,
) -> int:
    """Execute complete end-to-end persona pipeline."""
    if targets is None:
        targets = resolve_targets(raw_dir, batch=batch, limit=limit, faction=faction, groups=groups)
    target_groups = groups or sorted(targets.keys())

    if resume:
        before = len(target_groups)
        target_groups = [
            g for g in target_groups if not is_exported(output_dir, targets[g].astrbot_id)
        ]
        skipped = before - len(target_groups)
        if skipped:
            print(f"ℹ 断点续跑：跳过已生成的 {skipped} 位角色")
    if not target_groups:
        print("ℹ 没有需要处理的角色（全部已生成或名单为空）。")
        return 0

    print("=" * 80)
    print("   啾信 Juus Companion - 人设流水线 (Persona Pipeline v1)")
    print(f"   模式: {'批量名单驱动' if batch else '试点名单 (BATCH_1_SHIPS)'}")
    print(f"   目标角色数量: {len(target_groups)} 位")
    print(f"   原始数据目录: {raw_dir}")
    print(f"   输出交付目录: {output_dir}")
    print("=" * 80)

    # 1. Fetching layer
    print("\n[Step 1/5] 导入层：检查并拉取上游游戏数据源...")
    fetcher = Fetcher(raw_dir=raw_dir)
    if not offline:
        try:
            fetched_files = fetcher.fetch_all(force=force_fetch)
            print(f"✓ 成功同步/载入 {len(fetched_files)} 个上游配置表，已更新 manifest.json")
        except Exception as e:
            logger.error("拉取数据失败: %s", e)
            if not any(raw_dir.glob("**/*.json")):
                print("❌ 错误：本地无可用配置表且网络拉取失败。")
                return 1
            print("⚠️ 网络拉取异常，尝试回退使用现有本地缓存...")
    else:
        print("✓ 离线模式：跳过网络拉取，直接使用本地缓存")

    # 2. Extraction layer
    print("\n[Step 2/5] 抽取层：聚合角色私聊、动态、语音台词与档案...")
    aggregator = RawDataAggregator(raw_dir=raw_dir)
    materials = aggregator.extract_batch(target_groups, targets=targets)

    print("\n" + "-" * 78)
    print(f"{'角色名':<16} {'ship_group':<10} {'阵营':<8} {'私聊话题':<8} {'台词数':<8} {'誓约/EX':<8} {'音频链':<8}")
    print("-" * 78)
    for g in target_groups:
        mat = materials[g]
        st = mat.stats
        print(
            f"{mat.name_cn:<16} {mat.ship_group:<10} {mat.faction_cn:<8} "
            f"{st.chat_topics_count:<8} {st.total_voicelines_count:<8} "
            f"{st.oath_and_ex_voicelines_count:<8} {st.audio_links_count:<8}"
        )
    print("-" * 78)

    # 3. Generation layer
    print("\n[Step 3/5] 生成层：构建 SillyTavern V2 角色卡与三层世界书 (L0/L1/L2)...")
    llm_client = LLMClient()
    llm_online = False if offline else llm_client.is_available()
    if llm_online:
        print(f"✓ 检测到在线模型网关: {llm_client.base_url} (模型: {llm_client.model})")
    else:
        print("ℹ 使用内置规则与高质量模板引擎（确定性高保真模式）")

    builder = PersonaBuilder(llm_client=llm_client if llm_online else None)
    cards: Dict[int, Dict] = {}
    for g in target_groups:
        mat = materials[g]
        card = builder.build_sillytavern_v2(mat)
        cards[g] = card
    print(f"✓ 已完成全部 {len(cards)} 位角色的卡片与世界书构建")

    # 4. Validation layer
    print("\n[Step 4/5] 质检层：执行称呼、口癖、禁忌词、一致性与基线自动检查...")
    validator = CharacterValidator()
    qa_report = validator.validate_batch(cards, materials)

    print("\n质检概览:")
    for sm in qa_report.character_summaries:
        status_str = "PASS" if sm.passed else "FAIL"
        print(f"  - [{status_str}] {sm.name_cn} (ship_group: {sm.ship_group}): 得分 {sm.score}/100")
        for r in sm.results:
            if not r.passed:
                print(f"      * {r.rule_name}: {r.message}")

    output_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = output_dir / "validation_report.json"
    report_md_path = output_dir / "validation_report.md"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": qa_report.generated_at,
                "total_characters": qa_report.total_characters,
                "passed_characters": qa_report.passed_characters,
                "average_score": qa_report.average_score,
                "summaries": [
                    {
                        "ship_group": s.ship_group,
                        "name_cn": s.name_cn,
                        "faction_cn": s.faction_cn,
                        "passed": s.passed,
                        "score": s.score,
                        "results": [
                            {
                                "rule_id": r.rule_id,
                                "rule_name": r.rule_name,
                                "passed": r.passed,
                                "severity": r.severity,
                                "message": r.message,
                            }
                            for r in s.results
                        ],
                    }
                    for s in qa_report.character_summaries
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(qa_report.to_markdown())
    print(f"✓ 质检报告已输出: {report_md_path}")

    # 5. Export layer
    print("\n[Step 5/5] 导出层：生成 SillyTavern V2、世界书、AstrBot 与啾信大脑多格式交付物...")
    for g in target_groups:
        mat = materials[g]
        card = cards[g]
        cid = mat.astrbot_id

        # 1. SillyTavern V2 Card
        st_path = output_dir / "sillytavern" / f"{cid}_sillytavern_v2.json"
        export_sillytavern_card(card, st_path)

        # 2. Standalone Lorebook
        lore_layers = assemble_three_layer_lorebook(mat)
        lore_path = output_dir / "lorebook" / f"{cid}_lorebook.json"
        export_standalone_lorebook(lore_layers, lore_path)

        # 3. AstrBot Persona
        astr_persona = builder.build_astrbot_persona(mat)
        astr_path = output_dir / "astrbot" / f"{cid}_astrbot.json"
        export_astrbot_persona(astr_persona, astr_path)

        # 4. Juus Brain Intermediate Schema
        brain_path = output_dir / "juus_brain" / f"{cid}_juus_brain.json"
        export_juus_brain_format(card, mat, brain_path)

    # Sidecar persona name mapping for AstrBot
    astrbot_names = {materials[g].astrbot_id: materials[g].name_cn for g in target_groups}
    names_path = output_dir / "astrbot" / "persona_names.json"
    export_astrbot_persona_names(astrbot_names, names_path)

    print(f"✓ 已成功导出全套格式到: {output_dir.resolve()}")

    # 6. L0/L1 worldbooks (once per run, shared across characters)
    print("\n[Step 6/6] 世界书层：导出 L0 母港通用 / L1 阵营世界书（全员共享）...")
    faction_keys = [materials[g].faction_key for g in target_groups]
    l0l1_files = export_l0_l1_lorebooks(output_dir, faction_keys)
    print(f"✓ L0/L1 世界书已导出 ({len(l0l1_files)} 个文件)")

    print("=" * 80)
    if qa_report.passed_characters == qa_report.total_characters:
        print("   人设流水线运行完毕！所有质检均已通过，交付物已齐备。")
    else:
        failed = qa_report.total_characters - qa_report.passed_characters
        print(
            f"   人设流水线运行完毕：{qa_report.passed_characters}/{qa_report.total_characters} 通过，"
            f"{failed} 未通过（详见质检报告）。"
        )
    print("=" * 80)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Juus Companion Persona Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run full pipeline from zero")
    run_parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="Raw data directory")
    run_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    run_parser.add_argument("--groups", type=int, nargs="*", default=None, help="Ship group IDs to run")
    run_parser.add_argument("--force-fetch", action="store_true", help="Force re-download raw files")
    run_parser.add_argument("--offline", action="store_true", help="Run without network access")
    run_parser.add_argument("--batch", action="store_true",
                            help="Batch mode: build full ship list from ship_data_statistics "
                                 "(CN primary, EN fallback) instead of BATCH_1_SHIPS")
    run_parser.add_argument("--limit", type=int, default=None,
                            help="Cap number of ships in batch mode (deterministic order)")
    run_parser.add_argument("--faction", type=str, default=None,
                            help="Filter batch mode by faction_key (e.g. eagle_union, meta_faction)")
    run_parser.add_argument("--resume", action="store_true",
                            help="Skip ships whose exports already exist (resume interrupted batch)")

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch raw data only")
    fetch_parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="Raw data directory")
    fetch_parser.add_argument("--force", action="store_true", help="Force re-download")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        fetcher = Fetcher(raw_dir=args.raw_dir)
        fetcher.fetch_all(force=args.force)
        print("Fetch completed.")
        return 0
    elif args.command == "run" or args.command is None:
        raw_dir = getattr(args, "raw_dir", DEFAULT_RAW_DIR)
        output_dir = getattr(args, "output_dir", DEFAULT_OUTPUT_DIR)
        groups = getattr(args, "groups", None)
        force_fetch = getattr(args, "force_fetch", False)
        offline = getattr(args, "offline", False)
        batch = getattr(args, "batch", False)
        limit = getattr(args, "limit", None)
        faction = getattr(args, "faction", None)
        resume = getattr(args, "resume", False)
        return run_pipeline(
            raw_dir=raw_dir,
            output_dir=output_dir,
            groups=groups,
            force_fetch=force_fetch,
            offline=offline,
            batch=batch,
            limit=limit,
            faction=faction,
            resume=resume,
        )
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
