"""Definitions of upstream data sources per docs/DATA_POLICY.md."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SourceItem:
    key: str
    rel_path: str
    urls: List[str]
    description: str
    required: bool = True


UPSTREAM_SOURCES: List[SourceItem] = [
    SourceItem(
        key="cn_stats",
        rel_path="CN/sharecfgdata/ship_data_statistics.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/sharecfgdata/ship_data_statistics.json",
        ],
        description="CN ship statistics table (group ID, name, nationality, stats)",
    ),
    SourceItem(
        key="cn_words",
        rel_path="CN/sharecfgdata/ship_skin_words.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/sharecfgdata/ship_skin_words.json",
        ],
        description="CN skin voicelines table (feeling1-5, propose, login, touch, main)",
    ),
    SourceItem(
        key="cn_words_extra",
        rel_path="CN/ShareCfg/ship_skin_words_extra.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/ShareCfg/ship_skin_words_extra.json",
        ],
        description="CN extra/post-oath skin voicelines (condition 1100 EX lines)",
    ),
    SourceItem(
        key="cn_chat_group",
        rel_path="CN/ShareCfg/activity_ins_chat_group.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/ShareCfg/activity_ins_chat_group.json",
        ],
        description="CN JUUs private chat topics and unlock criteria",
    ),
    SourceItem(
        key="cn_chat_lang",
        rel_path="CN/ShareCfg/activity_ins_chat_language.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/ShareCfg/activity_ins_chat_language.json",
        ],
        description="CN JUUs private chat dialogues and commander branches",
    ),
    SourceItem(
        key="cn_juus_template",
        rel_path="CN/ShareCfg/activity_ins_template.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/ShareCfg/activity_ins_template.json",
        ],
        description="CN JUUs timeline posts (ship_group, photo, comment links)",
    ),
    SourceItem(
        key="cn_juus_lang",
        rel_path="CN/ShareCfg/activity_ins_language.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/ShareCfg/activity_ins_language.json",
        ],
        description="CN JUUs post content and comment texts",
    ),
    SourceItem(
        key="cn_juus_npc",
        rel_path="CN/ShareCfg/activity_ins_npc_template.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/ShareCfg/activity_ins_npc_template.json",
        ],
        description="CN JUUs comments metadata (commenter ship_group, text link)",
    ),
    SourceItem(
        key="cn_memory",
        rel_path="CN/ShareCfg/memory_template.json",
        urls=[
            "https://raw.githubusercontent.com/AzurLaneTools/AzurLaneData/master/CN/ShareCfg/memory_template.json",
        ],
        description="CN memory template catalog (story script titles & indexes)",
    ),
    SourceItem(
        key="en_stats",
        rel_path="EN/sharecfgdata/ship_data_statistics.json",
        urls=[
            "https://raw.githubusercontent.com/Fernando2603/AzurLaneData/main/sharecfgdata/ship_data_statistics.json",
        ],
        description="EN ship statistics (for 2026 new ships like HMS Tiger)",
    ),
    SourceItem(
        key="en_words",
        rel_path="EN/sharecfgdata/ship_skin_words.json",
        urls=[
            "https://raw.githubusercontent.com/Fernando2603/AzurLaneData/main/sharecfgdata/ship_skin_words.json",
        ],
        description="EN skin voicelines (for 2026 new ships like HMS Tiger)",
    ),
    SourceItem(
        key="audio_voicelink",
        rel_path="audio/voicelink.json",
        urls=[
            "https://raw.githubusercontent.com/Fernando2603/AzurLane/main/voicelink.json",
        ],
        description="Audio .ogg voiceline direct link index (Fernando2603/AzurLane)",
        required=False,
    ),
]

