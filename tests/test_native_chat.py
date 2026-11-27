from __future__ import annotations

import json
import urllib.request
from threading import Thread

from pipeline.cli import BATCH_TAVERN_PIPELINE_FREEZE_MESSAGE, run_pipeline
from prototypes.native_chat.engine import LocalChatEngine, clean_model_output
from prototypes.native_chat.models import GatewayRouter, load_model_profiles
from prototypes.native_chat.personas import PERSONAS
from prototypes.native_chat.prompt import DailyContext, build_messages
from prototypes.native_chat.web import NativeChatHTTPServer


class FakeGateway:
    def complete(self, *, messages, metadata) -> str:
        assert messages[-2]["role"] == "user"
        if metadata["model_profile"] == "gemini-carbon":
            return "<bubble>*走近你*我在。</bubble><bubble>（看着你）先喝水。</bubble>"
        return "<bubble>嗯。</bubble><bubble>慢慢说。</bubble><bubble>我听着。</bubble>"


def make_engine() -> LocalChatEngine:
    profiles = load_model_profiles(
        {
            "JUUS_MODEL_BASE_URL": "http://127.0.0.1:9/v1",
            "JUUS_GEMINI_MODEL": "gemini-test",
            "JUUS_SONNET_MODEL": "sonnet-test",
        }
    )
    router = GatewayRouter({profile.id: FakeGateway() for profile in profiles}, profiles)
    return LocalChatEngine(router=router, context=DailyContext())


def test_model_profiles_accept_ninerouter_environment_without_printing_secrets():
    profiles = load_model_profiles(
        {
            "NINEROUTER_URL": "http://127.0.0.1:20128/v1",
            "NINEROUTER_KEY": "test-key",
            "NINEROUTER_SONNET_MODEL": "sonnet-router-alias",
        }
    )
    assert all(profile.configured for profile in profiles)
    assert all(profile.api_key_env == "NINEROUTER_KEY" for profile in profiles)
    assert (
        dict((profile.id, profile.model_name) for profile in profiles)["sonnet"]
        == "sonnet-router-alias"
    )


def test_native_personas_are_exactly_the_three_core_characters():
    assert [persona.id for persona in PERSONAS] == ["belfast", "enterprise", "ulrich"]
    for persona in PERSONAS:
        assert persona.examples
        assert "SillyTavern" not in persona.voice


def test_prompt_is_mobile_native_and_forbids_stage_play():
    prompt = build_messages(
        PERSONAS[0],
        history=[],
        user_text="今天有点累",
        context=DailyContext(),
    )
    system = prompt.messages[0]["content"]
    assert "1 到 4 个 <bubble>" in system
    assert "禁止星号动作旁白" in system
    assert "禁止大段自我介绍" in system
    assert "禁止无边界长独白" in system
    assert "SillyTavern" in system
    assert prompt.trace["format"] == "native-mobile-bubbles-v1"
    assert prompt.trace["context_injected"] is True


def test_clean_model_output_removes_stage_residue_and_macros():
    cleaned = clean_model_output("*拉起你的手* {{user}}，先休息\n旁白：她看着你")
    assert "*" not in cleaned
    assert "{{user}}" not in cleaned
    assert "旁白" not in cleaned
    assert "指挥官" in cleaned


def test_engine_returns_short_bubbles_and_keeps_model_lanes_separate():
    engine = make_engine()
    first = engine.send(
        character_id="ulrich",
        model_id="gemini-carbon",
        user_text="今天脑子好乱",
        include_context=True,
    )
    second = engine.send(
        character_id="ulrich",
        model_id="sonnet",
        user_text="今天脑子好乱",
        include_context=True,
    )

    assert 1 <= len(first.bubbles) <= 4
    assert [bubble.text for bubble in first.bubbles] == ["我在。", "先喝水。"]
    assert all(len(bubble.text) <= 40 for bubble in first.bubbles)
    assert all("*" not in bubble.text for bubble in first.bubbles)
    assert all("（" not in bubble.text for bubble in first.bubbles)
    assert [bubble.text for bubble in first.bubbles] != [bubble.text for bubble in second.bubbles]
    assert len(engine.history("ulrich", "gemini-carbon")) == 2
    assert len(engine.history("ulrich", "sonnet")) == 2


def test_compare_endpoint_returns_two_lanes():
    engine = make_engine()
    server = NativeChatHTTPServer(("127.0.0.1", 0), engine)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps(
            {"character_id": "belfast", "message": "晚饭还没吃", "include_context": False}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/compare",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert set(payload["results"]) == {"gemini-carbon", "sonnet"}
    assert all(result["ok"] for result in payload["results"].values())
    assert all(result["bubbles"] for result in payload["results"].values())


def test_batch_tavern_pipeline_is_frozen(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("JUUS_ALLOW_LEGACY_TAVERN_BATCH", raising=False)
    exit_code = run_pipeline(raw_dir=tmp_path, output_dir=tmp_path, offline=True, batch=True)
    assert exit_code == 2
    assert BATCH_TAVERN_PIPELINE_FREEZE_MESSAGE.split("；")[0] in capsys.readouterr().out
