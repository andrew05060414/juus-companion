from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from prototypes.demo_support import DemoOpenAIServer
from prototypes.shared.director import ScriptedDirector
from prototypes.shared.domain import Character, Group
from prototypes.shared.model_gateway import OpenAICompatibleGateway
from prototypes.shared.scheduler import ProactiveJob
from prototypes.shape_a import IndependentBrain
from prototypes.shape_c_prime import JuusAstrBotPlugin
from prototypes.shape_c_prime.astrbot_shim import (
    AstrBotRuntime,
    PLATFORM_ADAPTER_REGISTRY,
    PlatformEvent,
)


NOW = datetime(2026, 9, 26, 21, 0, tzinfo=timezone.utc)
CHARACTERS = (
    Character("aster", "Aster"),
    Character("briar", "Briar"),
    Character("cato", "Cato"),
)
GROUPS = (Group("test-group", ("aster", "briar", "cato"), max_rounds=3),)


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, metadata) -> str:
        self.calls.append({"messages": list(messages), "metadata": dict(metadata)})
        return f"{metadata['speaker_id']}::reply"


class PrototypeTests(unittest.TestCase):
    def test_shape_a_covers_single_group_skip_round_limit_and_proactive_ledger(self) -> None:
        gateway = RecordingGateway()
        brain = IndependentBrain(
            characters=CHARACTERS,
            groups=GROUPS,
            gateway=gateway,
            director=ScriptedDirector({"test-group": ("aster", "[SKIP]", "cato", "briar")}),
        )

        brain.send_single(character_id="aster", content="hello", now=NOW)
        group_run = brain.send_group(group_id="test-group", content="group hello", now=NOW)
        brain.schedule_proactive(
            ProactiveJob("a-job", NOW + timedelta(minutes=1), "briar", "dm:briar", "remind me")
        )
        proactive = brain.tick(now=NOW + timedelta(minutes=1))

        self.assertEqual([event.content for event in group_run.events if event.kind == "decision"], ["aster", "[SKIP]", "cato"])
        self.assertEqual([event.actor_id for event in group_run.events if event.kind == "message"], ["aster", "cato"])
        self.assertEqual(sum(event.kind == "skip" for event in group_run.events), 1)
        self.assertEqual(len(proactive), 1)
        self.assertEqual([record.status for record in brain.delivery_ledger], ["queued"])
        self.assertEqual(len(gateway.calls), 4)

    def test_shape_c_prime_uses_registered_adapter_and_host_scheduler(self) -> None:
        gateway = RecordingGateway()
        runtime = AstrBotRuntime()
        plugin = JuusAstrBotPlugin(
            runtime=runtime,
            characters=CHARACTERS,
            groups=GROUPS,
            gateway=gateway,
            director=ScriptedDirector({"test-group": ("aster", "[SKIP]", "cato", "briar")}),
        )

        self.assertIn("juus-local", PLATFORM_ADAPTER_REGISTRY)
        runtime.receive(PlatformEvent("single-message", "private-aster", "commander", "hello", NOW, target_character_id="aster"))
        runtime.receive(PlatformEvent("group-message", "group-channel", "commander", "group hello", NOW, "test-group"))
        plugin.schedule_proactive(
            ProactiveJob("c-job", NOW + timedelta(minutes=1), "briar", "private-briar", "remind me")
        )
        runtime.run_due(NOW + timedelta(minutes=1))

        self.assertEqual([event.content for event in plugin.events if event.kind == "decision"], ["aster", "[SKIP]", "cato"])
        self.assertEqual([event.actor_id for event in plugin.events if event.kind == "message"], ["aster", "cato"])
        self.assertEqual([record.status for record in plugin.delivery_ledger], ["queued"])
        self.assertEqual([message.origin for message in runtime.outbox], ["single", "group", "group", "proactive"])

    def test_openai_compatible_gateway_round_trip_uses_expected_envelope(self) -> None:
        with DemoOpenAIServer() as server:
            gateway = OpenAICompatibleGateway(server.base_url, model="test-model")
            reply = gateway.complete(
                messages=({"role": "user", "content": "synthetic prompt"},),
                metadata={"shape": "test", "speaker_id": "aster", "origin": "single"},
            )

            self.assertIn("synthetic prompt", reply)
            self.assertEqual(len(server.requests), 1)
            self.assertEqual(server.requests[0]["model"], "test-model")
            self.assertEqual(server.requests[0]["metadata"]["shape"], "test")


if __name__ == "__main__":
    unittest.main()
