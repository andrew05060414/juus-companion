"""Protocol tests use only invented dialogue and local candidate IDs."""

import pytest

from juus_server.bubbles import (
    BubblePolicy,
    bind_message_fields,
    history_backfill,
    parse_bubbles,
    render_bubbles,
)


def texts(result):
    return [bubble.text for bubble in result.bubbles]


def codes(result):
    return [warning.code for warning in result.warnings]


def test_standard_reply_preserves_order_and_ignores_outside_prose():
    result = parse_bubbles("说明\n<bubble>今天看云吗？</bubble>\n<bubble>我带画本。</bubble>")
    assert texts(result) == ["今天看云吗？", "我带画本。"]
    assert not result.used_fallback
    assert codes(result) == ["outside_tags_ignored"]


def test_missing_tags_and_long_lines_use_newlines_and_punctuation():
    result = parse_bubbles(
        "今天看云吗？\n我带画本。也带铅笔！再拿杯水。", policy=BubblePolicy(max_chars=7)
    )
    assert texts(result) == ["今天看云吗？", "我带画本。", "也带铅笔！", "再拿杯水。"]
    assert result.used_fallback


@pytest.mark.parametrize("tagged", [False, True])
def test_long_unpunctuated_line_has_bounded_chunks(tagged):
    output = "云" * 203
    if tagged:
        output = f"<bubble>{output}</bubble>"
    result = parse_bubbles(output)
    assert texts(result) == ["云" * 40] * 4
    assert "bubble_limit" in codes(result)
    assert texts(parse_bubbles("云" * 25, policy=BubblePolicy(max_chars=10))) == [
        "云" * 10,
        "云" * 10,
        "云" * 5,
    ]


@pytest.mark.parametrize(
    "source",
    ["（转身）", "(伸手（拿起画本）)（微笑）", "（跨行\n动作）", "（未闭合动作", "()（）"],
)
def test_all_actions_produce_empty_retry_result(source):
    result = parse_bubbles(f"<bubble>{source}</bubble>")
    assert result.bubbles == ()
    assert result.needs_retry
    assert "empty_reply" in codes(result)


def test_actions_removed_before_length_split_and_can_be_disabled():
    source = "<bubble>（拿起（蓝色）画本）云很好看。（微笑）</bubble>"
    assert texts(parse_bubbles(source)) == ["云很好看。"]
    assert "（" in texts(parse_bubbles(source, policy=BubblePolicy(strip_actions=False)))[0]
    assert texts(parse_bubbles("（跨行\n拿画笔）\n看云。")) == ["看云。"]


@pytest.mark.parametrize("label", ["语音", "表情"])
@pytest.mark.parametrize("wrapper", ["{}", "<bubble>{}</bubble>"])
def test_non_candidate_ids_are_always_dropped(label, wrapper):
    for index in range(100):
        result = parse_bubbles(
            wrapper.format(f"[{label}: invented_{index}]"),
            voice_candidates={"voice_ok": "虚构问候"},
            sticker_candidates={"sticker_ok": "虚构云朵"},
        )
        assert result.bubbles == ()
        assert "invalid_media_id" in codes(result)
        assert result.needs_retry


def test_media_candidates_are_exact_turn_local_and_kind_scoped():
    result = parse_bubbles(
        "<bubble>[语音: voice_ok]</bubble><bubble>[表情： sticker_ok]</bubble>"
        "<bubble>[语音: sticker_ok]</bubble><bubble>[语音: VOICE_OK]</bubble>",
        voice_candidates={"voice_ok": "虚构语音字幕"},
        sticker_candidates={"sticker_ok": "虚构纸风车"},
    )
    assert [bubble.kind for bubble in result.bubbles] == ["voice", "sticker"]
    assert texts(result) == ["虚构语音字幕", "虚构纸风车"]
    assert codes(result).count("invalid_media_id") == 2
    assert parse_bubbles("<bubble>[语音: voice_ok]</bubble>").bubbles == ()


@pytest.mark.parametrize(
    "source",
    [
        "正文[语音: made_up]",
        "[语音: voice_ok]附加文本",
        "[语音: voice_ok][表情: sticker_ok]",
        "[语音: incomplete",
        "[表情: ]",
        "（[语音: made_up]）正常文字",
    ],
)
def test_mixed_or_malformed_media_cannot_bypass_candidate_checks(source):
    result = parse_bubbles(
        f"<bubble>{source}</bubble>",
        voice_candidates={"voice_ok": "虚构字幕"},
        sticker_candidates={"sticker_ok": "虚构表情"},
        policy=BubblePolicy(max_chars=3),
    )
    assert not result.bubbles
    assert all(not hasattr(warning, "content") for warning in result.warnings)


def test_blank_candidate_text_fails_closed():
    result = parse_bubbles("<bubble>[语音: voice_ok]</bubble>", voice_candidates={"voice_ok": " "})
    assert not result.bubbles
    assert "invalid_media_id" in codes(result)


@pytest.mark.parametrize("strip_actions", [True, False])
def test_multiline_broken_media_does_not_escape_as_plain_text(strip_actions):
    result = parse_bubbles(
        "[语音:\nunknown]\n画稿准备好了。",
        policy=BubblePolicy(strip_actions=strip_actions),
    )
    assert texts(result) == ["画稿准备好了。"]
    assert "malformed_media_bubble" in codes(result)


def test_over_four_keeps_first_four_valid_bubbles_and_renumbers_after_filtering():
    result = parse_bubbles(
        "<bubble>[语音: unknown]</bubble>"
        + "".join(f"<bubble>第{i}朵云</bubble>" for i in range(6))
    )
    assert texts(result) == [f"第{i}朵云" for i in range(4)]
    rows = bind_message_fields(
        result.bubbles,
        turn_id="synthetic-turn",
        bubble_index=10,
        types={"text": "plain", "voice": "audio", "sticker": "image"},
    )
    assert [row["bubble_index"] for row in rows] == [10, 11, 12, 13]
    assert all(row["turn_id"] == "synthetic-turn" and row["type"] == "plain" for row in rows)
    assert "bubble_limit" in codes(result)


@pytest.mark.parametrize("source", ["", " \n\t", "<bubble> </bubble>", "<bubble></bubble>\n<boo"])
def test_empty_does_not_invent_dialogue_or_throw(source):
    result = parse_bubbles(source)
    assert not result.bubbles
    assert result.needs_retry


def test_partial_tags_recover_without_leaking_known_tag_edges():
    result = parse_bubbles("<bubble>云很好看。\n<bubble>一起画下来。")
    assert texts(result) == ["云很好看。", "一起画下来。"]
    assert result.used_fallback
    assert texts(parse_bubbles("<bubble>保留。</bubble><bubble>未完成")) == ["保留。"]


def test_backfill_uses_trusted_media_text_and_has_no_side_effects():
    result = parse_bubbles(
        "<bubble>来画画。</bubble><bubble>[语音: voice_ok]</bubble><bubble>[表情: sticker_ok]</bubble>",
        voice_candidates={"voice_ok": "虚构的问候字幕"},
        sticker_candidates={"sticker_ok": "虚构笑脸描述"},
    )
    expected = (
        "<bubble>来画画。</bubble>\n<bubble>[语音: 虚构的问候字幕]</bubble>\n"
        "<bubble>[表情: 虚构笑脸描述]</bubble>"
    )
    assert history_backfill(result.bubbles) == expected
    assert history_backfill(result.bubbles) == expected
    assert history_backfill(()) == ""
    assert [bubble.media_id for bubble in result.bubbles] == [None, "voice_ok", "sticker_ok"]


def test_normalization_is_idempotent_and_preserves_macro_boundaries():
    source = "云" * 37 + "{{user}}，来看。"
    normalized = render_bubbles(source)
    assert normalized.count("{{user}}") == 1
    assert normalized == render_bubbles(normalized)


@pytest.mark.parametrize(
    "kwargs", [{"max_chars": 0}, {"max_bubbles": 5}, {"max_tokens": 0}, {"typing_ms_per_char": -1}]
)
def test_bad_application_configuration_is_reported(kwargs):
    with pytest.raises(ValueError):
        BubblePolicy(**kwargs)


def test_200_script_synthesized_outputs(capsys):
    # 196 content-bearing replies plus four deliberately empty/unsafe replies.
    # Success denominator includes all 200; an empty reply is safe but not success.
    successes = fallback = action_inputs = action_residue = invalid_dropped = 0
    for index in range(200):
        text = f"第{index}张虚构画稿准备好了。"
        variants = [
            f"<bubble>{text}</bubble>",
            text + "\n一起看云。",
            f"<bubble>（收起（虚构）画笔）{text}</bubble>",
            f"<bubble>(整理画纸){text}</bubble>",
            "云" * (70 + index),
            f"<bubble>{text}",
            f"<bubble>{text}</bubble><bubble>[语音: unknown]</bubble>",
            f"<bubble>{text}</bubble><bubble>[表情: sticker_ok]</bubble>",
            "".join(f"<bubble>第{j}朵虚构云</bubble>" for j in range(7)),
            f"```\n<bubble>{text}</bubble>\n```",
        ]
        source = (
            variants[index % len(variants)]
            if index < 196
            else ["", "（转身）", "<bubble></bubble>", "<bubble>[语音: unknown]</bubble>"][
                index - 196
            ]
        )
        result = parse_bubbles(source, sticker_candidates={"sticker_ok": "虚构纸风车"})
        successes += bool(result.bubbles)
        fallback += result.used_fallback
        if any(char in source for char in "（("):
            action_inputs += 1
            action_residue += any(
                char in bubble.text for bubble in result.bubbles for char in "（()）"
            )
        if "[语音: unknown]" in source:
            assert all(
                bubble.media_id != "unknown" and "unknown" not in bubble.text
                for bubble in result.bubbles
            )
            invalid_dropped += 1
        assert len(result.bubbles) <= 4
        assert all(bubble.text.strip() for bubble in result.bubbles)
        if index >= 196:
            assert result.needs_retry
    assert successes / 200 >= 0.95
    assert action_residue / action_inputs < 0.05
    report = (
        f"synthetic=200 nonempty={successes}/200 ({successes / 2:.1f}%) "
        f"fallback={fallback} empty_retry={200 - successes} "
        f"action_residue={action_residue}/{action_inputs} invalid_media_dropped={invalid_dropped}/{invalid_dropped}"
    )
    # Keep a reproducible acceptance report visible under pytest -s.
    with capsys.disabled():
        print(report)
