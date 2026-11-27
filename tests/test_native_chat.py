from __future__ import annotations

import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest
from juus_server.bubbles import parse_bubbles

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


def test_placeholder_gateway_template_is_inert_and_ninerouter_fallback_wins():
    placeholder_only = load_model_profiles(
        {
            "JUUS_MODEL_BASE_URL": "https://model-gateway.example.invalid/v1",
            "JUUS_MODEL_API_KEY": "replace-with-a-local-secret",
        }
    )
    assert all(not profile.configured for profile in placeholder_only)

    with_router = load_model_profiles(
        {
            "JUUS_MODEL_BASE_URL": "https://model-gateway.example.invalid/v1",
            "JUUS_MODEL_API_KEY": "replace-with-a-local-secret",
            "NINEROUTER_URL": "http://127.0.0.1:20128/v1",
            "NINEROUTER_KEY": "test-key",
        }
    )
    assert all(profile.base_url == "http://127.0.0.1:20128/v1" for profile in with_router)
    assert all(profile.api_key_env == "NINEROUTER_KEY" for profile in with_router)


def test_lane_specific_endpoint_does_not_inherit_shared_gateway_key():
    profiles = load_model_profiles(
        {
            "JUUS_GEMINI_BASE_URL": "http://gemini.local/v1",
            "JUUS_MODEL_BASE_URL": "http://shared.local/v1",
            "JUUS_MODEL_API_KEY": "shared-test-key",
        }
    )
    by_id = {profile.id: profile for profile in profiles}
    assert by_id["gemini-carbon"].api_key_env != "JUUS_MODEL_API_KEY"
    assert by_id["sonnet"].api_key_env == "JUUS_MODEL_API_KEY"

    with_lane_key = load_model_profiles(
        {
            "JUUS_GEMINI_BASE_URL": "http://gemini.local/v1",
            "JUUS_GEMINI_API_KEY": "gemini-test-key",
            "JUUS_MODEL_BASE_URL": "http://shared.local/v1",
            "JUUS_MODEL_API_KEY": "shared-test-key",
        }
    )
    assert {profile.id: profile.api_key_env for profile in with_lane_key}["gemini-carbon"] == (
        "JUUS_GEMINI_API_KEY"
    )


def test_shared_gateway_url_and_key_stay_bound_to_the_same_source():
    juus_url_without_usable_juus_key = load_model_profiles(
        {
            "JUUS_MODEL_BASE_URL": "http://other-gateway.local/v1",
            "JUUS_MODEL_API_KEY": "replace-with-a-local-secret",
            "NINEROUTER_URL": "http://ninerouter.local/v1",
            "NINEROUTER_KEY": "ninerouter-test-key",
        }
    )
    assert all(
        profile.base_url == "http://other-gateway.local/v1"
        for profile in juus_url_without_usable_juus_key
    )
    assert all(
        profile.api_key_env != "NINEROUTER_KEY"
        for profile in juus_url_without_usable_juus_key
    )

    ninerouter_url_without_usable_ninerouter_key = load_model_profiles(
        {
            "JUUS_MODEL_BASE_URL": "https://model-gateway.example.invalid/v1",
            "JUUS_MODEL_API_KEY": "juus-test-key",
            "NINEROUTER_URL": "http://ninerouter.local/v1",
        }
    )
    assert all(
        profile.base_url == "http://ninerouter.local/v1"
        for profile in ninerouter_url_without_usable_ninerouter_key
    )
    assert all(
        profile.api_key_env != "JUUS_MODEL_API_KEY"
        for profile in ninerouter_url_without_usable_ninerouter_key
    )


def _capture_gateway_authorization(monkeypatch, env_template, secret_env, secret_value):
    captured_authorizations = []

    class CaptureHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            captured_authorizations.append(self.headers.get("Authorization"))
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = json.dumps(
                {"choices": [{"message": {"content": "<bubble>收到。</bubble>"}}]}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv(secret_env, secret_value)
        monkeypatch.delenv("JUUS_NATIVE_CHAT_NO_API_KEY", raising=False)
        env = {
            name: value.format(port=server.server_port)
            for name, value in env_template.items()
        }
        router = GatewayRouter.from_profiles(load_model_profiles(env), timeout_seconds=2)
        router.complete(
            "gemini-carbon",
            messages=[{"role": "user", "content": "测试"}],
            metadata={"shape": "test", "speaker_id": "test", "origin": "test"},
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    return captured_authorizations


def test_cross_gateway_keys_are_not_sent_in_authorization_header(monkeypatch):
    juus_url_with_placeholder_key = _capture_gateway_authorization(
        monkeypatch,
        {
            "JUUS_MODEL_BASE_URL": "http://127.0.0.1:{port}/v1",
            "JUUS_MODEL_API_KEY": "replace-with-a-local-secret",
            "NINEROUTER_URL": "http://ninerouter.local/v1",
            "NINEROUTER_KEY": "ninerouter-test-key",
        },
        "NINEROUTER_KEY",
        "ninerouter-test-key",
    )
    assert juus_url_with_placeholder_key == [None]

    ninerouter_url_without_paired_key = _capture_gateway_authorization(
        monkeypatch,
        {
            "JUUS_MODEL_BASE_URL": "https://model-gateway.example.invalid/v1",
            "JUUS_MODEL_API_KEY": "juus-test-key",
            "NINEROUTER_URL": "http://127.0.0.1:{port}/v1",
        },
        "JUUS_MODEL_API_KEY",
        "juus-test-key",
    )
    assert ninerouter_url_without_paired_key == [None]


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


def test_clean_model_output_drops_stage_bubble_but_keeps_adjacent_legal_bubble():
    cleaned = clean_model_output("<bubble>旁白：她看着你</bubble><bubble>先喝水。</bubble>")
    assert "旁白" not in cleaned
    assert "她看着你" not in cleaned
    assert "<bubble>先喝水。</bubble>" in cleaned
    assert [bubble.text for bubble in parse_bubbles(cleaned).bubbles] == ["先喝水。"]


def test_clean_model_output_preserves_bubble_on_stage_line():
    cleaned = clean_model_output("旁白：她看着你 <bubble>先喝水。</bubble>")
    assert "旁白" not in cleaned
    assert "<bubble>先喝水。</bubble>" in cleaned


def test_clean_model_output_removes_multiline_asterisk_action():
    cleaned = clean_model_output("*她走近你\n又坐下* <bubble>先喝水。</bubble>")
    assert "走近" not in cleaned
    assert "坐下" not in cleaned
    assert "<bubble>先喝水。</bubble>" in cleaned


def test_clean_model_output_does_not_swallow_bubbles_between_unmatched_asterisks():
    cleaned = clean_model_output(
        "<bubble>收到*</bubble><bubble>马上来</bubble><bubble>*敬礼*</bubble>"
    )
    assert [bubble.text for bubble in parse_bubbles(cleaned).bubbles] == ["收到*", "马上来"]


def test_clean_model_output_keeps_arithmetic_asterisks_inside_separate_bubbles():
    cleaned = clean_model_output(
        "<bubble>3*5=15</bubble><bubble>2*4=8</bubble>"
    )
    assert [bubble.text for bubble in parse_bubbles(cleaned).bubbles] == ["3*5=15", "2*4=8"]


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


def test_write_endpoints_reject_non_json_and_cross_origin_requests():
    engine = make_engine()
    server = NativeChatHTTPServer(("127.0.0.1", 0), engine)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/chat"
        plain = urllib.request.Request(
            url,
            data=b"{}",
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as plain_error:
            urllib.request.urlopen(plain, timeout=5)
        assert plain_error.value.code == 403
        plain_error.value.close()

        cross_origin = urllib.request.Request(
            url,
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": "http://evil.example"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as origin_error:
            urllib.request.urlopen(cross_origin, timeout=5)
        assert origin_error.value.code == 403
        origin_error.value.close()

        same_origin = urllib.request.Request(
            url,
            data=json.dumps(
                {
                    "character_id": "belfast",
                    "model_id": "gemini-carbon",
                    "message": "晚饭还没吃",
                    "include_context": False,
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Origin": f"http://127.0.0.1:{server.server_port}",
            },
            method="POST",
        )
        with urllib.request.urlopen(same_origin, timeout=5) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("batch", [False, True])
def test_legacy_tavern_pipeline_is_frozen(monkeypatch, capsys, tmp_path, batch):
    monkeypatch.delenv("JUUS_ALLOW_LEGACY_TAVERN_BATCH", raising=False)
    exit_code = run_pipeline(raw_dir=tmp_path, output_dir=tmp_path, offline=True, batch=batch)
    assert exit_code == 2
    assert BATCH_TAVERN_PIPELINE_FREEZE_MESSAGE.split("；")[0] in capsys.readouterr().out
