"""Aggregator to parse raw tables into structured CharacterRawMaterial."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from pipeline.config import BATCH_1_SHIPS, NATIONALITY_MAP, ShipTargetConfig
from pipeline.extractor.models import (
    CharacterRawMaterial,
    ChatLine,
    ExtractionStats,
    JUUsChatTopic,
    JUUsComment,
    JUUsPost,
    StoryMemory,
    VoiceLine,
)
from pipeline.extractor.rules import VARIANT_MERGES, merge_variants

logger = logging.getLogger(__name__)


class RawDataAggregator:
    """Aggregates raw tables into per-character materials."""

    def __init__(self, raw_dir: Path):
        self.raw_dir = raw_dir
        self._cn_stats: Dict = {}
        self._en_stats: Dict = {}
        self._cn_words: Dict = {}
        self._en_words: Dict = {}
        self._cn_words_extra: Dict = {}
        self._cn_chat_groups: Dict = {}
        self._cn_chat_langs: Dict = {}
        self._cn_juus_template: Dict = {}
        self._cn_juus_lang: Dict = {}
        self._cn_juus_npc: Dict = {}
        self._cn_memory: Dict = {}
        self._voicelinks: Dict = {}
        self._loaded = False

    def load_tables(self) -> None:
        """Load all raw JSON tables into memory."""
        if self._loaded:
            return

        def _read(rel_path: str) -> Dict:
            p = self.raw_dir / rel_path
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return data if isinstance(data, dict) else {}
                except Exception as e:
                    logger.warning("Error reading %s: %s", p, e)
            return {}

        self._cn_stats = _read("CN/sharecfgdata/ship_data_statistics.json")
        self._en_stats = _read("EN/sharecfgdata/ship_data_statistics.json")
        self._cn_words = _read("CN/sharecfgdata/ship_skin_words.json")
        self._en_words = _read("EN/sharecfgdata/ship_skin_words.json")
        self._cn_words_extra = _read("CN/ShareCfg/ship_skin_words_extra.json")
        self._cn_chat_groups = _read("CN/ShareCfg/activity_ins_chat_group.json")
        self._cn_chat_langs = _read("CN/ShareCfg/activity_ins_chat_language.json")
        self._cn_juus_template = _read("CN/ShareCfg/activity_ins_template.json")
        self._cn_juus_lang = _read("CN/ShareCfg/activity_ins_language.json")
        self._cn_juus_npc = _read("CN/ShareCfg/activity_ins_npc_template.json")
        self._cn_memory = _read("CN/ShareCfg/memory_template.json")
        self._voicelinks = _read("audio/voicelink.json")
        self._loaded = True
        logger.info("Raw data tables loaded successfully.")

    def _find_ship_stat(self, ship_group: int, fallback_en: bool = False) -> Optional[dict]:
        """Find ship_data_statistics entry by ship_group (id // 10 == ship_group)."""
        stats_tables = [self._cn_stats, self._en_stats] if fallback_en else [self._cn_stats]
        for table in stats_tables:
            for k, v in table.items():
                if isinstance(v, dict):
                    sid = v.get("id", 0)
                    if sid // 10 == ship_group:
                        return v
        if not fallback_en and self._en_stats:
            # Try EN fallback if missing in CN
            for k, v in self._en_stats.items():
                if isinstance(v, dict) and v.get("id", 0) // 10 == ship_group:
                    return v
        return None

    def _extract_chat_topics(self, ship_group: int) -> List[JUUsChatTopic]:
        """Extract JUUs private chats for a given ship_group."""
        topics: List[JUUsChatTopic] = []
        for tid, tinfo in self._cn_chat_groups.items():
            if not isinstance(tinfo, dict):
                continue
            if tinfo.get("ship_group") == ship_group:
                name = tinfo.get("name", f"Topic_{tid}")
                unlock_desc = tinfo.get("unlock_desc", "")
                line_ids = tinfo.get("content", [])
                lines: List[ChatLine] = []
                for lid in line_ids:
                    lstr = str(lid)
                    linfo = self._cn_chat_langs.get(lstr)
                    if isinstance(linfo, dict):
                        sender = linfo.get("ship_group", 0)
                        text = linfo.get("param", "")
                        opts_raw = linfo.get("option", "")
                        opts: List[str] = []
                        if isinstance(opts_raw, list):
                            for opt_item in opts_raw:
                                if isinstance(opt_item, list) and len(opt_item) >= 2:
                                    opts.append(str(opt_item[1]))
                                elif isinstance(opt_item, str):
                                    opts.append(opt_item)
                        lines.append(
                            ChatLine(
                                id=lid,
                                sender_group=sender,
                                is_commander=(sender == 0),
                                text=text,
                                options=opts,
                            )
                        )
                topics.append(
                    JUUsChatTopic(
                        topic_id=int(tid) if str(tid).isdigit() else 0,
                        name=name,
                        unlock_desc=unlock_desc,
                        lines=lines,
                    )
                )
        return topics

    def _extract_juus_posts_and_replies(
        self, ship_group: int
    ) -> tuple[List[JUUsPost], List[JUUsComment]]:
        """Extract JUUs posts authored by character and replies made on other posts."""
        posts: List[JUUsPost] = []
        replies_made: List[JUUsComment] = []

        # Find posts made by this ship
        for pid, pinfo in self._cn_juus_template.items():
            if not isinstance(pinfo, dict):
                continue
            sg = pinfo.get("ship_group")
            msg_key = pinfo.get("message_persist", "")
            post_text = ""
            if msg_key and msg_key in self._cn_juus_lang:
                post_text = self._cn_juus_lang[msg_key].get("value", "")

            # Comments under this post
            discuss_ids = pinfo.get("npc_discuss_persist", [])
            post_comments: List[JUUsComment] = []
            if isinstance(discuss_ids, list):
                for cid in discuss_ids:
                    cinfo = self._cn_juus_npc.get(str(cid))
                    if isinstance(cinfo, dict):
                        csg = cinfo.get("ship_group", 0)
                        cmsg_key = cinfo.get("message_persist", "")
                        ctext = self._cn_juus_lang.get(cmsg_key, {}).get("value", "")
                        comment_obj = JUUsComment(comment_id=int(cid), sender_group=csg, text=ctext)
                        post_comments.append(comment_obj)
                        if csg == ship_group and sg != ship_group:
                            replies_made.append(comment_obj)

            if sg == ship_group and post_text:
                posts.append(
                    JUUsPost(
                        post_id=int(pid) if str(pid).isdigit() else 0,
                        author_group=sg,
                        text=post_text,
                        comments=post_comments,
                    )
                )

        return posts, replies_made

    def _extract_voicelines(
        self, ship_group: int, target_cfg: Optional[ShipTargetConfig] = None
    ) -> List[VoiceLine]:
        """Extract skin voicelines including feeling1-5, propose, and EX lines."""
        voicelines: List[VoiceLine] = []
        sg_str = str(ship_group)
        is_fallback = target_cfg.fallback_en if target_cfg else False

        words_tables = [self._en_words] if is_fallback else [self._cn_words, self._en_words]
        active_table = self._cn_words if (not is_fallback and any(k.startswith(sg_str) for k in self._cn_words)) else self._en_words

        # Skin words
        for skin_id, skin_data in active_table.items():
            if not isinstance(skin_data, dict) or not skin_id.startswith(sg_str):
                continue

            voice_links = self._voicelinks.get(skin_id, {})

            for vk, text_val in skin_data.items():
                if vk in ["id", "voice_key", "voice_key_2"] or not text_val or not isinstance(text_val, str):
                    continue

                # Main voicelines can be split by '|'
                parts = [p.strip() for p in text_val.split("|") if p.strip()]
                for idx, part in enumerate(parts):
                    vkey = f"{vk}_{idx+1}" if len(parts) > 1 else vk
                    audio_url = voice_links.get(vk) or voice_links.get(vkey)
                    is_oath = "propose" in vk or vk == "feeling5"
                    voicelines.append(
                        VoiceLine(
                            skin_id=skin_id,
                            voicekey=vkey,
                            text=part,
                            is_oath_or_ex=is_oath,
                            audio_url=audio_url,
                        )
                    )

        # Extra skin words (condition 1100 post-oath / EX lines)
        for skin_id, extra_data in self._cn_words_extra.items():
            if not isinstance(extra_data, dict) or not skin_id.startswith(sg_str):
                continue
            voice_links = self._voicelinks.get(skin_id, {})
            for vk, raw_val in extra_data.items():
                if vk == "id" or not isinstance(raw_val, list):
                    continue
                for item in raw_val:
                    if isinstance(item, list) and len(item) >= 2:
                        cond, text_str = item[0], item[1]
                        if not text_str or not isinstance(text_str, str):
                            continue
                        parts = [p.strip() for p in text_str.split("|") if p.strip()]
                        for idx, part in enumerate(parts):
                            vkey_ex = f"{vk}_ex_{idx+1}" if len(parts) > 1 else f"{vk}_ex"
                            audio_url = voice_links.get(f"{vk}_ex") or voice_links.get(vk)
                            voicelines.append(
                                VoiceLine(
                                    skin_id=skin_id,
                                    voicekey=vkey_ex,
                                    text=part,
                                    condition=cond,
                                    is_oath_or_ex=True,
                                    audio_url=audio_url,
                                )
                            )

        return voicelines

    def _extract_memories(self, character_name: str) -> List[StoryMemory]:
        """Extract memories / story catalog items matching character name."""
        memories: List[StoryMemory] = []
        short_name = character_name.split("·")[-1].replace("（", "").replace("）", "")
        for mid, minfo in self._cn_memory.items():
            if not isinstance(minfo, dict):
                continue
            title = minfo.get("title", "")
            condition = minfo.get("condition", "")
            story = minfo.get("story", "")
            if (short_name and short_name in title) or (short_name and short_name in condition):
                memories.append(
                    StoryMemory(
                        memory_id=int(mid) if str(mid).isdigit() else 0,
                        title=title,
                        story=story,
                    )
                )
        return memories

    def extract_single(
        self,
        ship_group: int,
        target_cfg: Optional[ShipTargetConfig] = None,
    ) -> CharacterRawMaterial:
        """Extract all materials for a single ship_group."""
        self.load_tables()
        cfg = target_cfg or BATCH_1_SHIPS.get(ship_group)
        stat = self._find_ship_stat(ship_group, fallback_en=cfg.fallback_en if cfg else False)

        name_cn = cfg.name_cn if cfg else (stat.get("name", f"Ship_{ship_group}") if stat else f"Ship_{ship_group}")
        name_en = cfg.name_en if cfg else (stat.get("english_name", "") if stat else "")
        astrbot_id = cfg.astrbot_id if cfg else f"ship_{ship_group}"

        nat_id = stat.get("nationality", 0) if stat else 0
        nat_info = NATIONALITY_MAP.get(nat_id, {"key": "other", "name": "其他", "english_name": "Other"})
        faction_key = cfg.faction_key if cfg else nat_info["key"]
        faction_cn = cfg.faction_cn if cfg else nat_info["name"]

        # Skins
        sg_str = str(ship_group)
        skin_ids = sorted(
            list(
                set(
                    [k for k in self._cn_words.keys() if k.startswith(sg_str)]
                    + [k for k in self._en_words.keys() if k.startswith(sg_str)]
                )
            )
        )

        chat_topics = self._extract_chat_topics(ship_group)
        juus_posts, juus_replies = self._extract_juus_posts_and_replies(ship_group)
        voicelines = self._extract_voicelines(ship_group, target_cfg=cfg)
        memories = self._extract_memories(name_cn)

        notes = []
        if cfg and cfg.fallback_en:
            notes.append("CN 数据缺失，已从 Fernando2603/AzurLaneData 补充 [pending_cn_supplement]")
        if cfg and cfg.notes:
            notes.append(cfg.notes)

        mat = CharacterRawMaterial(
            ship_group=ship_group,
            name_cn=name_cn,
            name_en=name_en,
            astrbot_id=astrbot_id,
            faction_key=faction_key,
            faction_cn=faction_cn,
            ship_type=str(stat.get("type", "")) if stat else "",
            skin_ids=skin_ids,
            chat_topics=chat_topics,
            juus_posts=juus_posts,
            juus_replies=juus_replies,
            voicelines=voicelines,
            story_memories=memories,
            notes=notes,
        )
        mat.calculate_stats()
        return mat

    def extract_batch(
        self,
        ship_groups: Optional[List[int]] = None,
    ) -> Dict[int, CharacterRawMaterial]:
        """Extract materials for a list of ship_groups, applying variant merges."""
        groups = ship_groups or list(BATCH_1_SHIPS.keys())
        self.load_tables()

        # Check if any variant groups need to be extracted
        all_required_groups: Set[int] = set(groups)
        for g in groups:
            if g in VARIANT_MERGES:
                all_required_groups.update(VARIANT_MERGES[g])

        extracted: Dict[int, CharacterRawMaterial] = {}
        for g in all_required_groups:
            cfg = BATCH_1_SHIPS.get(g)
            extracted[g] = self.extract_single(g, target_cfg=cfg)

        # Apply variant merges
        result: Dict[int, CharacterRawMaterial] = {}
        for g in groups:
            canonical = extracted[g]
            if g in VARIANT_MERGES:
                variants = [extracted[vg] for vg in VARIANT_MERGES[g] if vg in extracted]
                canonical = merge_variants(canonical, variants)
            result[g] = canonical

        return result

