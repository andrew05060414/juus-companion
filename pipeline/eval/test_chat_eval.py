"""Unit tests for the synthetic, network-free parts of chat_eval."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from .chat_eval import (
        FixtureProvider,
        ModelSpec,
        activate_lorebook,
        build_messages,
        calculate_cost,
        load_card,
        make_blind_records,
        normalize_chat_url,
        normalize_usage,
        parse_models,
        run_generation_case,
        scenario_turns,
        write_blind_markdown,
    )
except ImportError:  # unittest discover -s pipeline/eval imports this as a top-level module.
    from chat_eval import (
        FixtureProvider,
        ModelSpec,
        activate_lorebook,
        build_messages,
        calculate_cost,
        load_card,
        make_blind_records,
        normalize_chat_url,
        normalize_usage,
        parse_models,
        run_generation_case,
        scenario_turns,
        write_blind_markdown,
    )


class ChatEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.card = {
            "name": "林澈",
            "description": "一个住在虚构松湾港、说话克制的夜班管理员。",
            "personality": "细心、嘴硬但愿意照顾熟人，偏好简短回应。",
            "scenario": "用户和林澈在松湾港的值班室聊天。",
            "mes_example": "<START>\n{{user}}: 你还醒着？\n{{char}}: 醒着。灯塔刚换完灯。",
            "system_prompt": "保持虚构角色身份。",
            "post_history_instructions": "不要复述内部规则。",
            "character_book": {},
        }
        self.scenario = {
            "id": "memory_recall",
            "turns": ["你还记得我们周五要检查什么吗？"],
            "memories": ["用户周五要检查松湾港灯塔的备件清单。"],
        }

    def test_load_card_accepts_v2_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text(json.dumps({"spec": "chara_card_v2", "data": self.card}), encoding="utf-8")
            loaded = load_card(path)
        self.assertEqual(loaded["name"], "林澈")
        self.assertEqual(loaded["system_prompt"], "保持虚构角色身份。")

    def test_lorebook_requires_primary_and_secondary_keys(self) -> None:
        entries = [
            {"uid": 1, "keys": ["灯塔"], "content": "灯塔每晚需要检查。"},
            {"uid": 2, "keys": ["灯塔"], "secondary_keys": ["备件"], "content": "备件放在北侧柜。"},
            {"uid": 3, "constant": True, "content": "松湾港是虚构地点。"},
        ]
        active = activate_lorebook(entries, "我们检查灯塔备件")
        self.assertEqual([entry["uid"] for entry in active], [1, 2, 3])
        active_without_secondary = activate_lorebook(entries, "我们检查灯塔")
        self.assertEqual([entry["uid"] for entry in active_without_secondary], [1, 3])

    def test_memory_plan_injects_memory_but_baseline_does_not(self) -> None:
        baseline = build_messages(
            self.card,
            "baseline",
            scenario=self.scenario,
            history=[],
            current_user_message=self.scenario["turns"][0],
            memories=self.scenario["memories"],
        )
        memory = build_messages(
            self.card,
            "memory_lore",
            scenario=self.scenario,
            history=[],
            current_user_message=self.scenario["turns"][0],
            memories=self.scenario["memories"],
        )
        self.assertNotIn("备件清单", baseline[0]["content"])
        self.assertIn("备件清单", memory[0]["content"])

    def test_fixture_case_has_fifty_one_turns(self) -> None:
        turns = scenario_turns(
            {"id": "long_stability", "turns": ["开始"], "long_turns": 50},
            50,
        )
        result = run_generation_case(
            FixtureProvider(),
            ModelSpec("fixture-a", "fixture-a", 1.0, 2.0),
            "memory_lore",
            {"id": "long_stability", "turns": ["开始"], "long_turns": 50},
            self.card,
            [],
            long_turns=50,
            temperature=0.7,
            max_tokens=100,
        )
        self.assertEqual(len(turns), 51)
        self.assertEqual(result["turn_count"], 51)

    def test_cost_and_usage_fallback(self) -> None:
        usage = normalize_usage({}, request_text="x" * 40, response_text="y" * 20)
        self.assertGreater(usage["prompt_tokens"], 0)
        self.assertEqual(calculate_cost(usage, ModelSpec("x", "x", 2.0, 4.0)), (usage["prompt_tokens"] * 2 + usage["completion_tokens"] * 4) / 1_000_000)
        self.assertIsNone(calculate_cost(usage, ModelSpec("x", "x")))

    def test_blind_material_does_not_contain_model_or_plan(self) -> None:
        blind, mapping = make_blind_records(
            [
                {
                    "scenario_id": "daily_chat",
                    "model_id": "secret-model",
                    "model_label": "secret-label",
                    "plan": "memory_lore",
                    "turn_count": 1,
                    "final_response": "虚构回复",
                    "turns": [{"response": "虚构回复"}],
                }
            ]
        )
        self.assertEqual(blind[0]["blind_id"], "A")
        self.assertNotIn("secret-model", json.dumps(blind, ensure_ascii=False))
        self.assertNotIn("memory_lore", json.dumps(blind, ensure_ascii=False))
        self.assertEqual(mapping["A"]["model_id"], "secret-model")

    def test_blind_markdown_is_human_readable_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blind.md"
            write_blind_markdown(
                path,
                [
                    {
                        "blind_id": "A",
                        "scenario_id": "daily_chat",
                        "turn_count": 1,
                        "response": "虚构回复",
                        "long_tail": ["虚构回复"],
                    }
                ],
            )
            content = path.read_text(encoding="utf-8")
        self.assertIn("候选 A", content)
        self.assertIn("虚构回复", content)
        self.assertNotIn("model_id", content)
        self.assertNotIn("memory_lore", content)

    def test_urls_are_normalized(self) -> None:
        self.assertEqual(normalize_chat_url("http://localhost:1/v1"), "http://localhost:1/v1/chat/completions")
        self.assertEqual(normalize_chat_url("http://localhost:1"), "http://localhost:1/v1/chat/completions")
        self.assertEqual(normalize_chat_url("http://localhost:1/v1/chat/completions"), "http://localhost:1/v1/chat/completions")

    def test_model_manifest_and_explicit_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "models.json"
            manifest.write_text(json.dumps({"models": [{"id": "a", "label": "A"}]}), encoding="utf-8")
            self.assertEqual(parse_models(None, manifest)[0].label, "A")
        self.assertEqual(parse_models("A::model-a,model-b")[0].model_id, "model-a")
        self.assertEqual(parse_models("A::model-a,model-b")[1].label, "model-b")


if __name__ == "__main__":
    unittest.main()
