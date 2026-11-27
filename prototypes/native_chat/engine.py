"""In-memory local chat engine for the three-persona native prototype."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count

from juus_server.bubbles import Bubble, parse_bubbles

from .models import GatewayRouter, ModelProfile
from .personas import PERSONA_BY_ID, PERSONAS, NativePersona
from .prompt import DailyContext, build_messages

_ASTERISK_ACTION = re.compile(r"[*＊][\s\S]{1,160}?[*＊]")
_TEMPLATE_MACRO = re.compile(r"\{\{[^{}\r\n]+\}\}")
_STAGE_LINE = re.compile(r"^\s*(?:旁白|场景|动作|舞台|narration|action)\s*[:：]", re.IGNORECASE)
_BUBBLE_TAG = re.compile(r"<bubble>(.*?)</bubble>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class EngineReply:
    model_id: str
    model_label: str
    bubbles: tuple[Bubble, ...]
    raw_reply: str
    warnings: tuple[str, ...]
    created_at: str
    elapsed_ms: int
    configured: bool


@dataclass(frozen=True, slots=True)
class EngineError:
    model_id: str
    model_label: str
    error: str
    configured: bool


def _without_stage_lines(text: str) -> str:
    lines = [line for line in text.splitlines() if not _STAGE_LINE.search(line)]
    return "\n".join(lines).strip()


def _clean_output_segment(text: str) -> str:
    cleaned = _TEMPLATE_MACRO.sub("指挥官", text)
    cleaned = _ASTERISK_ACTION.sub("", cleaned)
    return _without_stage_lines(cleaned)


def clean_model_output(text: str) -> str:
    """Remove stage-play residue inside each bubble or untagged segment."""
    parts: list[str] = []
    position = 0
    for match in _BUBBLE_TAG.finditer(text):
        outside = _clean_output_segment(text[position : match.start()])
        if outside:
            parts.append(outside)
        bubble_text = _clean_output_segment(match.group(1))
        if bubble_text:
            parts.append(f"<bubble>{bubble_text}</bubble>")
        position = match.end()
    tail = _clean_output_segment(text[position:])
    if tail:
        parts.append(tail)
    return "\n".join(parts).strip()


def _history_window(
    items: Sequence[Mapping[str, str]], limit: int = 14
) -> tuple[dict[str, str], ...]:
    return tuple({"role": item["role"], "content": item["content"]} for item in items[-limit:])


class LocalChatEngine:
    def __init__(
        self,
        *,
        router: GatewayRouter,
        personas: Mapping[str, NativePersona] | None = None,
        context: DailyContext | None = None,
    ) -> None:
        self.router = router
        self.personas = dict(personas or PERSONA_BY_ID)
        self.context = context or DailyContext()
        self._histories: dict[tuple[str, str], list[dict[str, str]]] = {}
        self._ids = count(1)

    def list_personas(self) -> list[dict[str, str]]:
        return [
            {
                "id": persona.id,
                "display_name": persona.display_name,
                "english_name": persona.english_name,
                "faction": persona.faction,
            }
            for persona in PERSONAS
            if persona.id in self.personas
        ]

    def list_models(self) -> list[dict[str, object]]:
        return [
            {
                "id": profile.id,
                "label": profile.label,
                "model_name": profile.model_name,
                "configured": profile.configured,
            }
            for profile in self.router.profiles
        ]

    def history(self, character_id: str, model_id: str) -> list[dict[str, str]]:
        return list(self._histories.get((character_id, model_id), []))

    def send(
        self,
        *,
        character_id: str,
        model_id: str,
        user_text: str,
        include_context: bool = False,
    ) -> EngineReply:
        persona = self._persona(character_id)
        profile = self._profile(model_id)
        text = user_text.strip()
        if not text:
            raise ValueError("message cannot be empty")
        key = (character_id, model_id)
        history = self._histories.setdefault(key, [])
        user_row = {
            "role": "user",
            "content": text,
            "id": f"u-{next(self._ids)}",
            "at": self._now(),
        }
        prompt = build_messages(
            persona,
            history=_history_window(history),
            user_text=text,
            context=self.context if include_context else None,
        )
        history.append(user_row)
        started = time.monotonic()
        raw = self.router.complete(
            model_id,
            messages=prompt.messages,
            metadata={
                "shape": "native-local-prototype",
                "speaker_id": persona.id,
                "origin": "single",
                "model_profile": model_id,
            },
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        cleaned = clean_model_output(raw)
        parsed = parse_bubbles(cleaned)
        if not parsed.bubbles:
            raise RuntimeError("model returned no usable chat bubble after de-tavern cleanup")
        assistant_content = "\n".join(
            f"<bubble>{bubble.text}</bubble>" for bubble in parsed.bubbles
        )
        history.append(
            {
                "role": "assistant",
                "content": assistant_content,
                "id": f"a-{next(self._ids)}",
                "at": self._now(),
                "model_id": model_id,
            }
        )
        return EngineReply(
            model_id=model_id,
            model_label=profile.label,
            bubbles=parsed.bubbles,
            raw_reply=raw,
            warnings=tuple(warning.code for warning in parsed.warnings),
            created_at=user_row["at"],
            elapsed_ms=elapsed_ms,
            configured=profile.configured,
        )

    def compare(
        self,
        *,
        character_id: str,
        user_text: str,
        include_context: bool = False,
    ) -> dict[str, EngineReply | EngineError]:
        results: dict[str, EngineReply | EngineError] = {}
        with ThreadPoolExecutor(max_workers=len(self.router.profiles)) as executor:
            futures = {
                executor.submit(
                    self.send,
                    character_id=character_id,
                    model_id=profile.id,
                    user_text=user_text,
                    include_context=include_context,
                ): profile
                for profile in self.router.profiles
            }
            for future in as_completed(futures):
                profile = futures[future]
                try:
                    results[profile.id] = future.result()
                except Exception as exc:
                    results[profile.id] = EngineError(
                        model_id=profile.id,
                        model_label=profile.label,
                        error=str(exc),
                        configured=profile.configured,
                    )
        return results

    def _persona(self, character_id: str) -> NativePersona:
        try:
            return self.personas[character_id]
        except KeyError as exc:
            raise ValueError(f"unknown character: {character_id}") from exc

    def _profile(self, model_id: str) -> ModelProfile:
        for profile in self.router.profiles:
            if profile.id == model_id:
                return profile
        raise ValueError(f"unknown model profile: {model_id}")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
