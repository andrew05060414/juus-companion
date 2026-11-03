"""Exercise template conversion with exclusively synthetic source materials."""

import re

from pipeline.generator.builder import PersonaBuilder
from server.src.juus_server.bubbles import BubblePolicy, parse_bubbles
from tests.test_generator import create_fictional_character


def assert_bubble_reply(text, max_chars=40):
    bodies = re.findall(r"<bubble>(.*?)</bubble>", text, re.DOTALL)
    assert 1 <= len(bodies) <= 4
    assert all(body.strip() and len(body) <= max_chars for body in bodies)
    assert not re.sub(r"<bubble>.*?</bubble>", "", text, flags=re.DOTALL).strip()
    assert not any(char in text for char in "（）()")


def test_first_mes_alternates_and_phi_follow_the_same_policy():
    builder = PersonaBuilder(
        bubble_policy=BubblePolicy(
            max_chars=18, max_bubbles=3, max_tokens=180, typing_ms_per_char=10
        )
    )
    card = builder.build_sillytavern_v2(create_fictional_character())["data"]
    assert_bubble_reply(card["first_mes"], 18)
    for greeting in card["alternate_greetings"]:
        assert_bubble_reply(greeting, 18)
    for field in ("post_history_instructions", "system_prompt"):
        assert "1~3 条气泡" in card[field]
        assert "18 字" in card[field]
        assert "<bubble>…</bubble>" in card[field]
        assert "自然融入神态动作" not in card[field]
        assert "用括号注明" not in card[field]
    assert builder.bubble_policy.max_tokens == 180
    assert builder.bubble_policy.typing_ms_per_char == 10


def test_examples_keep_user_turns_start_markers_and_multiline_boundaries():
    builder = PersonaBuilder()
    source = (
        "<START>\n{{user}}: （看看云）你好。\n{{char}}: （抬头）\n你好。\n一起画云？\n"
        "{{user}}: 好。\n{{char}}: <bubble>给你画笔。</bubble>\n\n"
        "<START>\n{{user}}: 谢谢。\n{{char}}: 不客气。"
    )
    output = builder._bubble_examples(source)
    assert output.count("<START>") == 2
    assert "{{user}}: （看看云）你好。" in output
    assert "{{user}}: 好。" in output
    assistants = re.findall(
        r"\{\{char\}\}: (.*?)(?=\n\{\{user\}\}:|\n*<START>|$)", output, re.DOTALL
    )
    assert len(assistants) == 3
    for assistant in assistants:
        assert_bubble_reply(assistant)
    assert output == builder._bubble_examples(output)


def test_topic_examples_and_voiceline_fallback_remain_dialogue():
    raw = create_fictional_character()
    builder = PersonaBuilder()
    examples = builder._generate_mes_examples(raw)
    assert "{{char}}: <bubble>指挥官，极光升起来了。</bubble>" in examples
    assert "{{user}}: 真美啊。" in examples
    raw.chat_topics = []
    examples = builder._generate_mes_examples(raw)
    assert "{{char}}: <bubble>指挥官，今天也要保持元气。</bubble>" in examples
    assert "{char}:" not in examples.replace("{{char}}:", "")
    assert "（指挥官，今天也要保持元气。）" not in examples


def test_action_only_assistant_example_is_omitted_without_inventing_a_reply():
    source = "<START>\n{{char}}: （挥手）\n{{user}}: 来画云。\n{{char}}: 好。"
    output = PersonaBuilder()._bubble_examples(source)
    assert output.count("{{char}}:") == 1
    assert "{{user}}: 来画云。" in output
    assert "{{char}}: <bubble>好。</bubble>" in output


def test_no_source_fallback_still_produces_nonempty_greetings_and_examples():
    raw = create_fictional_character()
    raw.chat_topics = []
    raw.voicelines = []
    data = PersonaBuilder().build_sillytavern_v2(raw)["data"]
    assert_bubble_reply(data["first_mes"])
    assert "{{char}}: <bubble>" in data["mes_example"]


def test_astrbot_assistant_examples_match_the_shared_system_prompt():
    persona = PersonaBuilder().build_astrbot_persona(create_fictional_character())
    assert "<bubble>…</bubble>" in persona["system_prompt"]
    for index, text in enumerate(persona["begin_dialogs"]):
        if index % 2:
            assert_bubble_reply(text)
        else:
            assert "<bubble>" not in text


def test_template_helpers_are_repeatable_and_keep_user_macros():
    raw = create_fictional_character()
    raw.voicelines[0].text = "指挥官，{{user}}，来画云吧。"
    builder = PersonaBuilder()
    first = builder.build_sillytavern_v2(raw)
    assert first == builder.build_sillytavern_v2(raw)
    assert "{{user}}" in first["data"]["first_mes"]
    assert not parse_bubbles(first["data"]["first_mes"]).needs_retry
