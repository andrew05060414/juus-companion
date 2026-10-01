"""Data models for extracted character raw materials."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ChatLine:
    id: int
    sender_group: int
    is_commander: bool
    text: str
    options: List[str] = field(default_factory=list)


@dataclass
class JUUsChatTopic:
    topic_id: int
    name: str
    unlock_desc: str
    lines: List[ChatLine] = field(default_factory=list)


@dataclass
class JUUsComment:
    comment_id: int
    sender_group: int
    text: str


@dataclass
class JUUsPost:
    post_id: int
    author_group: int
    text: str
    comments: List[JUUsComment] = field(default_factory=list)


@dataclass
class VoiceLine:
    skin_id: str
    voicekey: str
    text: str
    condition: Optional[int] = None
    is_oath_or_ex: bool = False
    audio_url: Optional[str] = None


@dataclass
class StoryMemory:
    memory_id: int
    title: str
    story: str


@dataclass
class ExtractionStats:
    chat_topics_count: int = 0
    chat_lines_count: int = 0
    juus_posts_count: int = 0
    juus_comments_made_count: int = 0
    total_voicelines_count: int = 0
    oath_and_ex_voicelines_count: int = 0
    audio_links_count: int = 0
    memories_count: int = 0

    def summary(self) -> str:
        return (
            f"JUUs私聊话题: {self.chat_topics_count} 个 ({self.chat_lines_count} 句), "
            f"JUUs动态: {self.juus_posts_count} 条, 评论: {self.juus_comments_made_count} 条, "
            f"台词: {self.total_voicelines_count} 条 (含誓约/EX: {self.oath_and_ex_voicelines_count} 条), "
            f"音频直链: {self.audio_links_count} 条, 关联剧情: {self.memories_count} 段"
        )


@dataclass
class CharacterRawMaterial:
    ship_group: int
    name_cn: str
    name_en: str
    astrbot_id: str
    faction_key: str
    faction_cn: str
    ship_type: str = ""
    cv: str = ""
    skin_ids: List[str] = field(default_factory=list)
    chat_topics: List[JUUsChatTopic] = field(default_factory=list)
    juus_posts: List[JUUsPost] = field(default_factory=list)
    juus_replies: List[JUUsComment] = field(default_factory=list)
    voicelines: List[VoiceLine] = field(default_factory=list)
    story_memories: List[StoryMemory] = field(default_factory=list)
    merged_groups: List[int] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    stats: ExtractionStats = field(default_factory=ExtractionStats)

    def calculate_stats(self) -> ExtractionStats:
        chat_lines_cnt = sum(len(t.lines) for t in self.chat_topics)
        oath_cnt = sum(1 for v in self.voicelines if v.is_oath_or_ex)
        audio_cnt = sum(1 for v in self.voicelines if v.audio_url)
        self.stats = ExtractionStats(
            chat_topics_count=len(self.chat_topics),
            chat_lines_count=chat_lines_cnt,
            juus_posts_count=len(self.juus_posts),
            juus_comments_made_count=len(self.juus_replies),
            total_voicelines_count=len(self.voicelines),
            oath_and_ex_voicelines_count=oath_cnt,
            audio_links_count=audio_cnt,
            memories_count=len(self.story_memories),
        )
        return self.stats

