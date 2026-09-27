"""Variant merging and fallback rules for character extraction."""

from __future__ import annotations

from typing import Dict, List
from pipeline.extractor.models import CharacterRawMaterial


# Ship variant merges: e.g. Yorktown (10705) + Yorktown II (10710)
# Key: canonical ship_group, Value: list of variant ship_groups to merge in
VARIANT_MERGES: Dict[int, List[int]] = {
    10705: [10710],
}

# Ships that must remain completely separate (e.g. META ships)
META_ISOLATED_GROUPS: List[int] = [
    970201,  # Helena META
    970708,  # Yorktown META (excluded from Batch 1, kept independent)
]


def merge_variants(
    canonical: CharacterRawMaterial,
    variants: List[CharacterRawMaterial],
) -> CharacterRawMaterial:
    """Merge variant materials into canonical character record."""
    for var in variants:
        canonical.skin_ids.extend([s for s in var.skin_ids if s not in canonical.skin_ids])
        canonical.chat_topics.extend(var.chat_topics)
        canonical.juus_posts.extend(var.juus_posts)
        canonical.juus_replies.extend(var.juus_replies)
        canonical.voicelines.extend(var.voicelines)
        canonical.story_memories.extend(var.story_memories)
        canonical.merged_groups.append(var.ship_group)
        canonical.notes.append(
            f"已合并变体形态: {var.name_cn} ({var.name_en}, ship_group={var.ship_group}) 视为后期心智觉醒形态"
        )
    canonical.calculate_stats()
    return canonical

