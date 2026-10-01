"""Small, transport-neutral domain types for the M0 spike."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


SKIP_TOKEN = "[SKIP]"


@dataclass(frozen=True)
class Character:
    """A fictional chat member used by the prototype."""

    id: str
    name: str


@dataclass(frozen=True)
class Group:
    id: str
    member_ids: tuple[str, ...]
    max_rounds: int = 3

    def __post_init__(self) -> None:
        if not self.member_ids:
            raise ValueError("a group needs at least one member")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be positive")


@dataclass(frozen=True)
class ChatMessage:
    id: str
    conversation_id: str
    sender_id: str
    role: str
    content: str
    created_at: datetime
    origin: str
    turn_id: str | None = None

    def as_model_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class GroupEvent:
    kind: str
    round_number: int
    actor_id: str | None
    content: str


@dataclass(frozen=True)
class GroupRun:
    group_id: str
    turn_id: str
    events: tuple[GroupEvent, ...]


@dataclass(frozen=True)
class DeliveryRecord:
    message_id: str
    conversation_id: str
    origin: str
    status: str
    attempts: int
