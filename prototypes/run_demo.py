"""Run the same acceptance scenario against both brain-shape prototypes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from prototypes.demo_support import DemoOpenAIServer
from prototypes.shared.director import ScriptedDirector
from prototypes.shared.domain import Character, Group
from prototypes.shared.model_gateway import OpenAICompatibleGateway
from prototypes.shared.scheduler import ProactiveJob
from prototypes.shape_a import IndependentBrain
from prototypes.shape_c_prime import JuusAstrBotPlugin
from prototypes.shape_c_prime.astrbot_shim import AstrBotRuntime, PlatformEvent


CHARACTERS = (
    Character("aster", "Aster"),
    Character("briar", "Briar"),
    Character("cato", "Cato"),
)
GROUPS = (Group("test-group", ("aster", "briar", "cato"), max_rounds=3),)
NOW = datetime(2026, 9, 26, 21, 0, tzinfo=timezone.utc)


def build_gateway(base_url: str) -> OpenAICompatibleGateway:
    return OpenAICompatibleGateway(base_url, model="m0-demo")


def run_shape_a(base_url: str) -> dict[str, Any]:
    brain = IndependentBrain(
        characters=CHARACTERS,
        groups=GROUPS,
        gateway=build_gateway(base_url),
        director=ScriptedDirector({"test-group": ("aster", "[SKIP]", "cato", "briar")}),
    )
    single = brain.send_single(character_id="aster", content="今天先做一个小实验。", now=NOW)
    group_run = brain.send_group(group_id="test-group", content="请大家各说一句。", now=NOW)
    brain.schedule_proactive(
        ProactiveJob(
            id="a-reminder",
            due_at=NOW + timedelta(minutes=1),
            character_id="briar",
            conversation_id="dm:briar",
            prompt="这是一个测试提醒。",
        )
    )
    proactive = brain.tick(now=NOW + timedelta(minutes=1))
    return {
        "shape": brain.shape_name,
        "single": {"sender": single.sender_id, "text": single.content},
        "group_decisions": [event.content for event in group_run.events if event.kind == "decision"],
        "group_messages": [
            {"sender": event.actor_id, "text": event.content}
            for event in group_run.events
            if event.kind == "message"
        ],
        "group_skips": sum(event.kind == "skip" for event in group_run.events),
        "round_limit": GROUPS[0].max_rounds,
        "proactive": [{"sender": message.sender_id, "text": message.content} for message in proactive],
        "delivery_ledger": [record.status for record in brain.delivery_ledger],
    }


def run_shape_c_prime(base_url: str) -> dict[str, Any]:
    runtime = AstrBotRuntime()
    plugin = JuusAstrBotPlugin(
        runtime=runtime,
        characters=CHARACTERS,
        groups=GROUPS,
        gateway=build_gateway(base_url),
        director=ScriptedDirector({"test-group": ("aster", "[SKIP]", "cato", "briar")}),
    )
    runtime.receive(
        plugin_event(
            message_id="c-single",
            channel_id="private-aster",
            sender_id="commander",
            text="今天先做一个小实验。",
            now=NOW,
            target_character_id="aster",
        )
    )
    runtime.receive(
        plugin_event(
            message_id="c-group",
            channel_id="group-channel",
            sender_id="commander",
            text="请大家各说一句。",
            now=NOW,
            group_id="test-group",
        )
    )
    plugin.schedule_proactive(
        ProactiveJob(
            id="c-reminder",
            due_at=NOW + timedelta(minutes=1),
            character_id="briar",
            conversation_id="private-briar",
            prompt="这是一个测试提醒。",
        )
    )
    runtime.run_due(NOW + timedelta(minutes=1))
    group_decisions = [event.content for event in plugin.events if event.kind == "decision"]
    return {
        "shape": plugin.shape_name,
        "adapter_registered": "juus-local" in runtime.adapters,
        "single": next(message.text for message in runtime.outbox if message.origin == "single"),
        "group_decisions": group_decisions,
        "group_messages": [
            {"sender": event.actor_id, "text": event.content}
            for event in plugin.events
            if event.kind == "message"
        ],
        "group_skips": sum(event.kind == "skip" for event in plugin.events),
        "round_limit": GROUPS[0].max_rounds,
        "proactive": [message.text for message in runtime.outbox if message.origin == "proactive"],
        "delivery_ledger": [record.status for record in plugin.delivery_ledger],
    }


def plugin_event(
    *,
    message_id: str,
    channel_id: str,
    sender_id: str,
    text: str,
    now: datetime,
    group_id: str | None = None,
    target_character_id: str | None = None,
) -> PlatformEvent:

    return PlatformEvent(message_id, channel_id, sender_id, text, now, group_id, target_character_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shape", choices=("a", "c-prime", "both"), default="both")
    args = parser.parse_args()
    with DemoOpenAIServer() as gateway_server:
        results = []
        if args.shape in {"a", "both"}:
            results.append(run_shape_a(gateway_server.base_url))
        if args.shape in {"c-prime", "both"}:
            results.append(run_shape_c_prime(gateway_server.base_url))
        print(json.dumps({"results": results, "gateway_requests": gateway_server.request_count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
