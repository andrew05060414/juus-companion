"""Pure bubble protocol helpers; no gateway, storage, logging or framework I/O."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

BubbleKind = Literal["text", "voice", "sticker"]
_TAGS = re.compile(r"<bubble\s*>(.*?)</bubble\s*>", re.DOTALL | re.IGNORECASE)
_TAG_EDGE = re.compile(r"</?bubble\s*>", re.IGNORECASE)
_MEDIA = re.compile(r"\[(语音|表情)[ \t]*[:：][ \t]*([^\]\r\n]*)\]")
_MEDIA_START = re.compile(r"\[(?:语音|表情)\s*[:：]")


@dataclass(frozen=True, slots=True)
class BubblePolicy:
    """Tunable starting values, not measurements or gateway/client settings."""

    max_chars: int = 40
    max_bubbles: int = 4
    strip_actions: bool = True
    max_tokens: int = 300
    typing_ms_per_char: float = 35

    def __post_init__(self) -> None:
        if self.max_chars < 1 or not 1 <= self.max_bubbles <= 4:
            raise ValueError("max_chars must be positive; max_bubbles must be between 1 and 4")
        if self.max_tokens < 1 or self.typing_ms_per_char < 0:
            raise ValueError("max_tokens must be positive; typing_ms_per_char cannot be negative")


DEFAULT_BUBBLE_POLICY = BubblePolicy()


@dataclass(frozen=True, slots=True)
class Bubble:
    kind: BubbleKind
    # For media this is the server candidate's transcript/description, never model text.
    text: str
    media_id: str | None = None


@dataclass(frozen=True, slots=True)
class TraceWarning:
    """Safe metadata for the caller to persist in prompt_trace (no raw content)."""

    code: str
    source_index: int | None = None


@dataclass(frozen=True, slots=True)
class ParseResult:
    bubbles: tuple[Bubble, ...]
    warnings: tuple[TraceWarning, ...]
    used_fallback: bool

    @property
    def needs_retry(self) -> bool:
        return not self.bubbles


def _without_actions(text: str) -> str:
    # Strip nested, mixed-width parentheses, including truncated action tails.
    depth = 0
    kept = []
    for char in text:
        if char in "（(":
            depth += 1
        elif char in "）)":
            depth = max(0, depth - 1)
        elif depth == 0:
            kept.append(char)
    return "".join(kept)


def _short_parts(text: str, limit: int) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= limit:
        return [text] if text else []
    sentences = re.findall(r"[^。！？!?～~…]+[。！？!?～~…]*|[。！？!?～~…]+", text)
    parts = []
    for sentence in sentences:
        current = ""
        # Preserve SillyTavern macros even at a length boundary.
        for unit in re.findall(r"\{\{[^{}\n]+\}\}|.", sentence):
            if current and len(current) + len(unit) > limit:
                parts.append(current.strip())
                current = ""
            current += unit
        if current.strip():
            parts.append(current.strip())
    return parts


def _fallback_sources(text: str, strip_actions: bool) -> list[str]:
    # Keep actions/media together so malformed interiors cannot become dialogue.
    sources = []
    current = []
    depth = 0
    in_media = False
    for index, char in enumerate(text):
        if _MEDIA_START.match(text, index):
            in_media = True
        elif char == "]":
            in_media = False
        if strip_actions and char in "（(":
            depth += 1
        elif strip_actions and char in "）)":
            depth = max(0, depth - 1)
        if char in "\r\n" and depth == 0 and not in_media:
            sources.append("".join(current))
            current = []
        else:
            current.append(char)
    sources.append("".join(current))
    return sources


def parse_bubbles(
    output: str,
    *,
    voice_candidates: Mapping[str, str] | None = None,
    sticker_candidates: Mapping[str, str] | None = None,
    policy: BubblePolicy = DEFAULT_BUBBLE_POLICY,
) -> ParseResult:
    """Parse one completed model reply, returning warnings and an empty/retry signal.

    Candidate maps contain this turn's IDs and trusted transcript/description.
    Invalid or mixed media bubbles are dropped before cleanup or length splitting.
    Partial tags are recovered only when there are no complete tagged bubbles.
    """
    matches = list(_TAGS.finditer(output))
    warnings: list[TraceWarning] = []
    if matches:
        sources = [match.group(1) for match in matches]
        outside = _TAGS.sub("", output).strip()
        if outside:
            warnings.append(TraceWarning("outside_tags_ignored"))
    else:
        warnings.append(TraceWarning("fallback_split"))
        sources = _fallback_sources(_TAG_EDGE.sub("\n", output), policy.strip_actions)

    bubbles = []
    for index, source in enumerate(sources):
        source = source.strip()
        if not source:
            continue
        media = list(_MEDIA.finditer(source))
        if _MEDIA_START.search(source):
            valid = True
            for item in media:
                candidates = voice_candidates if item[1] == "语音" else sticker_candidates
                if not candidates or not candidates.get(item[2].strip(), "").strip():
                    warnings.append(TraceWarning("invalid_media_id", index))
                    valid = False
            if len(media) != 1 or media[0].group(0) != source:
                warnings.append(TraceWarning("malformed_media_bubble", index))
                valid = False
            if valid:
                item = media[0]
                candidates = voice_candidates if item[1] == "语音" else sticker_candidates
                media_id = item[2].strip()
                kind: BubbleKind = "voice" if item[1] == "语音" else "sticker"
                bubbles.append(Bubble(kind, candidates[media_id].strip(), media_id))
            continue
        if policy.strip_actions:
            source = _without_actions(source)
        # Remaining broken tag edges are format, not dialogue.
        source = _TAG_EDGE.sub("", source)
        bubbles.extend(Bubble("text", text) for text in _short_parts(source, policy.max_chars))

    if len(bubbles) > policy.max_bubbles:
        warnings.append(TraceWarning("bubble_limit"))
    kept = tuple(bubbles[: policy.max_bubbles])
    if not kept:
        warnings.append(TraceWarning("empty_reply"))
    return ParseResult(kept, tuple(warnings), used_fallback=not matches)


def render_bubbles(text: str, *, policy: BubblePolicy = DEFAULT_BUBBLE_POLICY) -> str:
    """Normalize a template reply with the same parser; no media allowed by default."""
    return "\n".join(
        f"<bubble>{bubble.text}</bubble>" for bubble in parse_bubbles(text, policy=policy).bubbles
    )


def history_backfill(bubbles: Sequence[Bubble]) -> str:
    """Render a recent-window assistant turn with media text instead of media IDs.

    Pass parsed/validated bubbles. This function does not mutate a window, fetch
    media, replay assets, or reparse its output as a model reply.
    """
    labels = {"voice": "语音", "sticker": "表情"}
    parts = []
    for bubble in bubbles:
        text = bubble.text
        if bubble.kind != "text":
            text = f"[{labels[bubble.kind]}: {text}]"
        parts.append(f"<bubble>{text}</bubble>")
    return "\n".join(parts)


def bind_message_fields(
    bubbles: Sequence[Bubble],
    *,
    turn_id: str,
    bubble_index: int,
    types: Mapping[BubbleKind, str],
) -> list[dict[str, str | int | None]]:
    """Illustrative boundary adapter, not a frozen #15 API or database model.

    Callers supply turn identity, first index and external type names explicitly.
    Regeneration/retries must obtain their identity from the owning chat engine.
    """
    return [
        {
            "turn_id": turn_id,
            "bubble_index": bubble_index + offset,
            "type": types[bubble.kind],
            "content": bubble.text,
            "media_id": bubble.media_id,
        }
        for offset, bubble in enumerate(bubbles)
    ]
