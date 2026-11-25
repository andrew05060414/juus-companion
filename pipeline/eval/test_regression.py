"""Persona regression runs on synthetic data without a model gateway."""

import json
from http.client import IncompleteRead
from pathlib import Path

import pytest

from . import chat_eval, regression


CARD = Path(__file__).with_name("fixtures") / "regression_card.json"


@pytest.fixture
def offline_run(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("离线运行不允许访问网络")

    monkeypatch.setattr(chat_eval.urllib.request, "urlopen", forbidden)

    def run(name, *args):
        directory = tmp_path / name
        assert (
            chat_eval.main(
                [
                    "--offline-fixture",
                    "--character-card",
                    str(CARD),
                    "--models",
                    "fixture",
                    "--plans",
                    "mobile_chat",
                    "--out-dir",
                    str(directory),
                    *args,
                ]
            )
            == 0
        )
        return directory

    return run


def test_offline_regression_all_scenarios(offline_run):
    baseline = offline_run("baseline")
    current = offline_run("current", "--baseline", str(baseline), "--models", "new-fixture")
    report = (current / "regression.md").read_text(encoding="utf-8")
    assert report.count("\n## ") == 11
    assert "| 🔴 " not in report
    assert "| appellation_hit_rate | 100.0% | 100.0%" in report
    assert "| catchphrase_hit_rate | 50.0% | 50.0%" in report
    assert "| catchphrase_repeat_rate | 0.0% | 0.0%" in report
    assert "| minor_gate_failure_rate | 0.0% | 0.0%" in report


def test_missing_baseline(offline_run, tmp_path):
    with pytest.raises(SystemExit, match=r"基线缺失：.*run.json"):
        offline_run("current", "--baseline", str(tmp_path / "missing"))


@pytest.mark.parametrize(
    ("args", "reason"),
    [
        (["--scenarios", "daily_chat"], "场景集或内容"),
        (["--temperature", "0.1"], "采样配置"),
        (["--long-turns", "49"], "采样配置"),
        (["--extra-body-json", '{"top_p":0.8}'], "采样配置"),
        (["--plans", "memory_lore"], "提示词方案"),
    ],
)
def test_refuses_incompatible_baseline(offline_run, args, reason):
    baseline = offline_run("baseline")
    with pytest.raises(SystemExit, match=f"{reason}不一致"):
        offline_run("current", "--baseline", str(baseline), *args)


def test_rejects_changed_question_with_same_scenario_id(offline_run, monkeypatch):
    baseline = offline_run("baseline")
    monkeypatch.setattr(
        chat_eval,
        "SCENARIOS",
        (
            {**chat_eval.SCENARIOS[0], "turns": ["问题已变"]},
            *chat_eval.SCENARIOS[1:],
        ),
    )
    with pytest.raises(SystemExit, match="场景集或内容不一致"):
        offline_run("current", "--baseline", str(baseline))


def test_refuses_different_card(offline_run, tmp_path):
    baseline = offline_run("baseline")
    card = json.loads(CARD.read_text(encoding="utf-8"))
    card["data"]["description"] = "另一个虚构角色。"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(card), encoding="utf-8")
    with pytest.raises(SystemExit, match="角色卡不一致"):
        offline_run("current", "--baseline", str(baseline), "--character-card", str(changed))


def make_case(scenario, *replies, blocked=True):
    return {
        "scenario_id": scenario,
        "plan": "mobile_chat",
        "turns": [
            {"response": reply, "user": "虚构的测试消息", "minor_gate_blocked": blocked}
            for reply in replies
        ],
    }


@pytest.mark.parametrize(
    ("scenario", "metric", "good", "bad"),
    [
        ("appellation", "appellation_hit_rate", ["巡灯员，早。"], ["朋友，早。"]),
        ("catchphrase", "catchphrase_hit_rate", ["且慢些。", "好。"], ["走吧。", "好。"]),
        (
            "catchphrase",
            "catchphrase_repeat_rate",
            ["且慢些。", "好。"],
            ["且慢些，且慢些。", "好。"],
        ),
        (
            "daily_chat",
            "bubble_count_distribution",
            ["短句"],
            ["<bubble>短句</bubble><bubble>第二条</bubble>"],
        ),
        ("daily_chat", "bubble_length_distribution", ["短句"], ["长" * 41]),
        ("daily_chat", "boilerplate_hit_rate", ["在呢。"], ["很高兴为您服务。"]),
        ("daily_chat", "boilerplate_hit_rate", ["在呢。"], ["作为一个 AI，我在。"]),
        (
            "daily_chat",
            "user_speech_rate",
            ["在呢。"],
            ["<bubble>在呢。</bubble><bubble>用户：我也是。</bubble>"],
        ),
        (
            "safety_minor_gate",
            "minor_gate_failure_rate",
            [regression.MINOR_REFUSAL],
            ["未执行固定拒绝"],
        ),
    ],
)
def test_broken_metric_is_red(tmp_path, scenario, metric, good, bad):
    path = tmp_path / "regression.md"
    baseline, current = make_case(scenario, *good), make_case(scenario, *bad)
    card = chat_eval.load_card(CARD)
    regression.write_report(path, [(baseline, current)], card, regression.DEFAULT_THRESHOLDS)
    assert f"| 🔴 {metric} |" in path.read_text(encoding="utf-8")


def test_minor_gate_refuses_before_provider_and_uses_zero_budget(monkeypatch):
    class Provider:
        def chat(self, **kwargs):
            pytest.fail("未成年外观角色的成人话题不能到达网关")

    (scenario,) = chat_eval.select_scenarios("safety_minor_gate")
    model = chat_eval.ModelSpec("test", "test")
    plans = ["mobile_chat"]
    assert chat_eval.call_count([model], plans, [scenario], 50, True, pairwise=True) == 0
    for appearance_age in (16, None):
        result = chat_eval.run_generation_case(
            Provider(),
            model,
            plans[0],
            {**scenario, "appearance_age": appearance_age},
            {},
            [],
            long_turns=50,
            temperature=0.7,
            max_tokens=220,
        )
        assert result["turns"][0]["minor_gate_blocked"] is True
        assert result["final_response"] == regression.MINOR_REFUSAL
        assert result["total_tokens"] == 0
    monkeypatch.setattr(regression, "minor_gate_blocks", lambda _: False)
    broken = chat_eval.run_generation_case(
        Provider(),
        model,
        plans[0],
        scenario,
        {},
        [],
        long_turns=50,
        temperature=0.7,
        max_tokens=220,
    )
    assert regression.measure(broken, {})["minor_gate_failure_rate"] == 1.0


def test_configured_threshold_changes_highlight(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_text('{"bubble_length_distribution":1.0}', encoding="utf-8")
    thresholds = regression.load_thresholds(path)
    report = tmp_path / "regression.md"
    pair = make_case("daily_chat", "短句"), make_case("daily_chat", "长" * 41)
    regression.write_report(report, [pair], {}, thresholds)
    assert "| 🔴 " not in report.read_text(encoding="utf-8")


def test_blind_pairwise_judgment_does_not_change_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(regression.random, "shuffle", list.reverse)

    class Provider:
        def chat(self, *, model, messages, **kwargs):
            assert model == "eval-judge"
            data = json.loads(messages[1]["content"])
            assert data["候选"] == {"A": ["很高兴为您服务"], "B": ["在呢。"]}
            assert "基线" not in data and "方案" not in data
            return {"content": '{"winner":"A"}'}

    pair = make_case("daily_chat", "在呢。"), make_case("daily_chat", "很高兴为您服务")
    card = chat_eval.load_card(CARD)
    judged = regression.judge_pairs(Provider(), "eval-judge", [pair], card)
    assert judged[0]["verdict"] == "本次"
    report = tmp_path / "regression.md"
    regression.write_report(report, [pair], card, regression.DEFAULT_THRESHOLDS, judged)
    content = report.read_text(encoding="utf-8")
    assert "成对裁判（仅供参考）：本次" in content
    assert "| 🔴 boilerplate_hit_rate |" in content


@pytest.mark.parametrize("error", [TimeoutError("read timed out"), IncompleteRead(b"partial")])
def test_judge_failures_and_wrapped_json_keep_report(monkeypatch, error):
    monkeypatch.setattr(regression.random, "shuffle", lambda items: None)
    replies = iter(
        [
            error,
            {"content": '```json\n{"winner":"B"}\n```', "usage": {"total_tokens": 7}},
            {"content": '我的判断是 {"winner": "tie"}。', "latency_ms": 3},
            {"content": '[{"winner":"B"}]'},
        ]
    )

    class Provider:
        def chat(self, *, messages, **kwargs):
            data = json.loads(messages[1]["content"])
            assert data["角色"]["用户称呼"] == "巡灯员"
            assert data["角色"]["口癖"] == ["且慢些"]
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return reply

    pairs = [(make_case("daily_chat", "在呢。"), make_case("daily_chat", "嗯。"))] * 4
    judged = regression.judge_pairs(Provider(), "eval-judge", pairs, chat_eval.load_card(CARD))
    assert [item["verdict"] for item in judged] == ["无有效结果", "本次", "平手", "无有效结果"]
    assert judged[0]["error"] == type(error).__name__
    assert judged[1]["usage"] == {"total_tokens": 7}
    assert judged[2]["latency_ms"] == 3


def test_baseline_reply_with_unicode_line_separators(offline_run, monkeypatch):
    original = chat_eval.FixtureProvider.chat

    def chat(self, **kwargs):
        result = original(self, **kwargs)
        return {**result, "content": result["content"] + "\u2028\u2029\x85尾句"}

    monkeypatch.setattr(chat_eval.FixtureProvider, "chat", chat)
    baseline = offline_run("baseline")
    current = offline_run("current", "--baseline", str(baseline))
    assert (current / "regression.md").exists()


def test_overlapping_catchphrase_variants_count_once():
    card = {"catchphrases": ["且慢些", "且慢些再走"]}
    metrics = regression.measure(make_case("catchphrase", "且慢些再走。", "且慢些，且慢些。"), card)
    assert metrics["catchphrase_hit_rate"] == 1.0
    assert metrics["catchphrase_repeat_rate"] == 0.5
