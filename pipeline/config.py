"""Configuration and constants for the Juus Companion persona pipeline."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Project root (directory containing AGENTS.md, docs, pipeline, etc.)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Default data directories (all inside data/, which is gitignored per DATA_POLICY.md)
DEFAULT_DATA_DIR = ROOT_DIR / "data"
DEFAULT_RAW_DIR = DEFAULT_DATA_DIR / "raw"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "output"

# Model gateway configuration (supports OpenAI compatible endpoints like 9router, Ollama, vLLM)
OPENAI_BASE_URL = (
    os.getenv("OPENAI_BASE_URL")
    or os.getenv("NINEROUTER_URL")
    or "http://localhost:11434/v1"
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or "ollama"
MODEL_NAME = (
    os.getenv("MODEL_NAME")
    or os.getenv("NINEROUTER_HAIKU_MODEL")
    or "qwen3.5:9b"
)


@dataclass
class ShipTargetConfig:
    ship_group: int
    id: str
    name_cn: str
    name_en: str
    astrbot_id: str
    faction_key: str
    faction_cn: str
    merged_groups: List[int] = field(default_factory=list)
    fallback_en: bool = False
    notes: str = ""


# First batch (首批 8 位角色) target definitions per Issue #2 & PX-402
BATCH_1_SHIPS: Dict[int, ShipTargetConfig] = {
    40503: ShipTargetConfig(
        ship_group=40503,
        id="ulrich_von_hutten",
        name_cn="乌尔里希·冯·胡滕",
        name_en="Ulrich von Hutten",
        astrbot_id="huteng",
        faction_key="iron_blood",
        faction_cn="铁血",
        notes="3 JUUs chat topics, 5 skin voice sets, vinyl music & health care demeanor",
    ),
    49902: ShipTargetConfig(
        ship_group=49902,
        id="friedrich_der_grosse",
        name_cn="腓特烈大帝",
        name_en="Friedrich der Grosse",
        astrbot_id="dadi",
        faction_key="iron_blood",
        faction_cn="铁血",
        notes="0 JUUs chat topics, 6 skin voice sets, maternal majesty & grand symphony demeanor",
    ),
    30510: ShipTargetConfig(
        ship_group=30510,
        id="musashi",
        name_cn="武藏",
        name_en="Musashi",
        astrbot_id="musashi",
        faction_key="sakura_empire",
        faction_cn="重樱",
        notes="0 JUUs chat topics, 4 skin voice sets, thunderous protectiveness & genmaicha demeanor",
    ),
    10702: ShipTargetConfig(
        ship_group=10702,
        id="lexington",
        name_cn="列克星敦",
        name_en="Lexington",
        astrbot_id="lexington",
        faction_key="eagle_union",
        faction_cn="白鹰",
        notes="6 JUUs chat topics, idol & elder sister demeanor",
    ),
    10705: ShipTargetConfig(
        ship_group=10705,
        id="yorktown",
        name_cn="约克城",
        name_en="Yorktown",
        astrbot_id="yorktown",
        faction_key="eagle_union",
        faction_cn="白鹰",
        merged_groups=[10710],  # Yorktown II (10710) is merged into Yorktown (10705)
        notes="Merged with Yorktown II (10710) as awakened progression; Yorktown META excluded",
    ),
    20516: ShipTargetConfig(
        ship_group=20516,
        id="lion",
        name_cn="狮",
        name_en="Lion",
        astrbot_id="lion",
        faction_key="royal_navy",
        faction_cn="皇家",
        notes="3 JUUs chat topics, regal & seductive royalty demeanor",
    ),
    970201: ShipTargetConfig(
        ship_group=970201,
        id="helena_meta",
        name_cn="海伦娜·META",
        name_en="Helena.META",
        astrbot_id="helena_meta",
        faction_key="meta_faction",
        faction_cn="META",
        notes="META independent persona, SG radar & fierce protective obsession",
    ),
    20238: ShipTargetConfig(
        ship_group=20238,
        id="tiger",
        name_cn="虎",
        name_en="Tiger",
        astrbot_id="tiger",
        faction_key="royal_navy",
        faction_cn="皇家",
        fallback_en=True,
        notes="2026 new ship, missing in CN AzurLaneData, fallback to EN data with [pending_cn_supplement]",
    ),
}

# Faction mapping based on nationality code in ship_data_statistics.
# Verified 2026-09-28 against BOTH CN (AzurLaneTools) and EN (Fernando2603)
# ship_data_statistics.json via hull prefixes in english_name:
#   6=RN (Regia Marina) -> 撒丁帝国, 7=SN (Soviet Navy) -> 北方联合,
#   8=FFNF (Free French) -> 自由鸢尾, 9=MNF (Vichy French) -> 维希教廷.
# NOTE: an earlier version of this map had 6/7/8/9 permuted; fixed per data.
NATIONALITY_MAP: Dict[int, Dict[str, str]] = {    1: {"key": "eagle_union", "name": "白鹰", "english_name": "Eagle Union"},
    2: {"key": "royal_navy", "name": "皇家", "english_name": "Royal Navy"},
    3: {"key": "sakura_empire", "name": "重樱", "english_name": "Sakura Empire"},
    4: {"key": "iron_blood", "name": "铁血", "english_name": "Iron Blood"},
    5: {"key": "dragon_empery", "name": "东煌", "english_name": "Dragon Empery"},
    6: {"key": "sardegna_empire", "name": "撒丁帝国", "english_name": "Sardegna Empire"},
    7: {"key": "northern_parliament", "name": "北方联合", "english_name": "Northern Parliament"},
    8: {"key": "iris_libre", "name": "自由鸢尾", "english_name": "Iris Libre"},
    9: {"key": "vichya_dominion", "name": "维希教廷", "english_name": "Vichya Dominion"},
    97: {"key": "meta_faction", "name": "META", "english_name": "META"},
}

# Baseline relationship requirements per Andrew's instructions: "已誓约 + 好感 200 + 满级"
DEFAULT_GAME_STATE = {
    "level": 125,
    "affinity": 200,
    "is_oath": True,
    "skins": [],
    "imported_from_game": False,
}


# ---------------------------------------------------------------------------
# Batch mode: list-driven ship registry (Issue #9)
# ---------------------------------------------------------------------------

# Numeric ship type code -> Chinese ship type name (verified against CN stats)
SHIP_TYPE_MAP: Dict[int, str] = {
    1: "驱逐舰",
    2: "轻巡洋舰",
    3: "重巡洋舰",
    4: "战列巡洋舰",
    5: "战列舰",
    6: "轻型航空母舰",
    7: "航空母舰",
    8: "潜艇",
    12: "维修舰",
    17: "潜水母舰",
    18: "大型巡洋舰",
    19: "补给舰",
}

# Playable ship nationalities: 9 factions + META(97).
# Excluded: 98 (Bulin enhancement material), 96/99/101-115 (collab ships,
# handled separately), siren units.
PLAYABLE_NATIONALITIES = {1, 2, 3, 4, 5, 6, 7, 8, 9, 97}


def slugify_astrbot_id(english_name: str, ship_group: int) -> str:
    """Build a deterministic ASCII persona id from the English ship name."""
    slug = english_name.strip().lower()
    slug = slug.replace(".meta", "_meta").replace("·", "_")
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    if not slug:
        slug = f"ship_{ship_group}"
    return slug


def build_ship_registry(
    cn_stats_path: "Path | str",
    en_stats_path: "Path | str | None" = None,
) -> Dict[int, ShipTargetConfig]:
    """Build the full batch target registry from ship_data_statistics tables.

    Rules:
    - CN table is primary; groups missing in CN fall back to the EN table
      (flagged with fallback_en=True and a [pending_cn_supplement] note).
    - Deduplicated by ship_group (id // 10); first CN entry wins.
    - META ships (nationality 97) stay independent (never merged).
    - Non-playable nationalities (Bulin, collab, sirens) are excluded.
    """
    from pathlib import Path as _Path

    def _load(p) -> Dict:
        p = _Path(p)
        if not p.exists():
            return {}
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    cn_stats = _load(cn_stats_path)
    en_stats = _load(en_stats_path) if en_stats_path else {}

    registry: Dict[int, ShipTargetConfig] = {}
    seen_slugs: Dict[str, int] = {}

    def _register(stat: dict, fallback_en: bool) -> None:
        group = int(stat.get("id", 0)) // 10
        if group in registry:
            return
        nat = stat.get("nationality", 0)
        nat_info = NATIONALITY_MAP.get(
            nat, {"key": "other", "name": "其他", "english_name": "Other"}
        )
        name_cn = stat.get("name") or f"Ship_{group}"
        name_en = stat.get("english_name") or name_cn
        slug = slugify_astrbot_id(name_en, group)
        if slug in seen_slugs:  # name collision (e.g. retrofit variants) -> suffix group id
            slug = f"{slug}_{group}"
        seen_slugs[slug] = group
        notes = ""
        if fallback_en:
            notes = "CN 数据缺失，已从 Fernando2603/AzurLaneData 补充 [pending_cn_supplement]"
        registry[group] = ShipTargetConfig(
            ship_group=group,
            id=slug,
            name_cn=name_cn,
            name_en=name_en,
            astrbot_id=slug,
            faction_key=nat_info["key"],
            faction_cn=nat_info["name"],
            fallback_en=fallback_en,
            notes=notes,
        )

    for _key, stat in cn_stats.items():
        if isinstance(stat, dict) and stat.get("nationality") in PLAYABLE_NATIONALITIES:
            _register(stat, fallback_en=False)
    for _key, stat in en_stats.items():
        if isinstance(stat, dict) and stat.get("nationality") in PLAYABLE_NATIONALITIES:
            _register(stat, fallback_en=True)

    return registry


def ship_type_cn(type_code: int) -> str:
    """Chinese display name for a numeric ship type code."""
    return SHIP_TYPE_MAP.get(type_code, "舰娘")

