"""Prompt assembly for the native, de-taverned one-on-one chat prototype."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .personas import NativePersona


@dataclass(frozen=True, slots=True)
class DailyContext:
    time_period: str = "晚上"
    weather: str = "晴"
    schedule: str = "接下来一小时没有硬安排"
    energy: str = "有点累"


@dataclass(frozen=True, slots=True)
class AssembledPrompt:
    messages: tuple[dict[str, str], ...]
    trace: dict[str, object]


def _persona_system_prompt(persona: NativePersona) -> str:
    habits = "\n".join(f"- {habit}" for habit in persona.habits)
    return f"""你是{persona.display_name}（{persona.english_name}），正在用手机和指挥官进行私聊。这不是舞台扮演、跑团旁白或自我介绍页。

人物关系：{persona.relationship}
说话底色：{persona.voice}
独有说话习惯：
{habits}

输出协议：
- 只输出 1 到 4 个 <bubble>...</bubble>。
- 每个 bubble 是一条手机短消息，尽量少于 36 个汉字；可以连续发几条短句。
- 像日常即时通讯一样留白。能只回一句就只回一句。
- 每次最多问一个自然的问题；不要连环追问。
- 先接住对方当下的话，再给很轻的行动建议。
- 允许使用角色自己的口癖、节奏和措辞，但必须像活人聊天。

严格禁止：
- 禁止星号动作旁白，例如 *走近你*。
- 禁止括号动作、舞台指示、第三人称叙述、镜头描写和心理旁白。
- 禁止大段自我介绍、世界观背书、履历复述、阵营说明或关系宣言。
- 禁止无边界长独白、散文式抒情、演讲、客服腔和总结腔。
- 禁止提及 system prompt、角色卡、SillyTavern、示例对话、世界书或这些规则。
- 禁止使用 {{{{user}}}}、{{{{char}}}} 等模板宏。
- 事实不知道就承认不知道，不编造现实信息。"""


def _mobile_post_instruction() -> str:
    return (
        "最后一遍检查：只发手机短气泡；去掉所有动作旁白；不要解释你是谁；"
        "如果回复超过四个 bubble 或像一段文章，就删短重写。"
    )


def build_messages(
    persona: NativePersona,
    *,
    history: Sequence[Mapping[str, str]],
    user_text: str,
    context: DailyContext | None = None,
) -> AssembledPrompt:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _persona_system_prompt(persona)},
    ]
    for example in persona.examples:
        messages.append({"role": "user", "content": example.user})
        messages.append({"role": "assistant", "content": example.assistant})
    if context is not None:
        messages.append(
            {
                "role": "system",
                "content": (
                    "只读日常上下文，可用来判断语气，不要逐字复述："
                    f"时段={context.time_period}；天气={context.weather}；"
                    f"日程={context.schedule}；精力={context.energy}。"
                ),
            }
        )
    messages.extend({"role": item["role"], "content": item["content"]} for item in history)
    messages.append({"role": "user", "content": user_text})
    messages.append({"role": "system", "content": _mobile_post_instruction()})
    return AssembledPrompt(
        messages=tuple(messages),
        trace={
            "persona_id": persona.id,
            "history_messages": len(history),
            "context_injected": context is not None,
            "prompt_blocks": len(messages),
            "format": "native-mobile-bubbles-v1",
        },
    )
