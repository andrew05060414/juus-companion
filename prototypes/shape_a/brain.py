"""A-shape prototype: the service owns conversations, routing, timers and ledger."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from prototypes.shared.director import ScriptedDirector
from prototypes.shared.domain import (
    Character,
    ChatMessage,
    DeliveryRecord,
    Group,
    GroupEvent,
    GroupRun,
    SKIP_TOKEN,
)
from prototypes.shared.model_gateway import ModelGateway
from prototypes.shared.scheduler import InMemoryScheduler, ProactiveJob


class IndependentBrain:
    """Self-contained orchestration boundary for shape A."""

    shape_name = "A-independent-service"

    def __init__(
        self,
        *,
        characters: Sequence[Character],
        groups: Sequence[Group],
        gateway: ModelGateway,
        director: ScriptedDirector,
        scheduler: InMemoryScheduler | None = None,
    ) -> None:
        self.characters = {character.id: character for character in characters}
        self.groups = {group.id: group for group in groups}
        self.gateway = gateway
        self.director = director
        self.scheduler = scheduler or InMemoryScheduler()
        self._messages: dict[str, list[ChatMessage]] = {}
        self.delivery_ledger: list[DeliveryRecord] = []
        self._sequence = 0

    def send_single(
        self,
        *,
        character_id: str,
        content: str,
        now: datetime,
    ) -> ChatMessage:
        self._require_character(character_id)
        conversation_id = f"dm:{character_id}"
        self._append_user_message(conversation_id, content, now, origin="single")
        return self._reply(
            conversation_id=conversation_id,
            character_id=character_id,
            now=now,
            origin="single",
            turn_id=None,
        )

    def send_group(
        self,
        *,
        group_id: str,
        content: str,
        now: datetime,
    ) -> GroupRun:
        group = self.groups[group_id]
        conversation_id = f"group:{group_id}"
        turn_id = self._next_id("turn")
        self._append_user_message(conversation_id, content, now, origin="group", turn_id=turn_id)
        events: list[GroupEvent] = []
        for round_number in range(1, group.max_rounds + 1):
            history = tuple(self._messages.get(conversation_id, ()))
            choice = self.director.choose(
                group_id=group_id,
                member_ids=group.member_ids,
                history=history,
                round_number=round_number,
            )
            events.append(GroupEvent("decision", round_number, choice, choice))
            if choice == SKIP_TOKEN:
                events.append(GroupEvent("skip", round_number, None, SKIP_TOKEN))
                continue
            reply = self._reply(
                conversation_id=conversation_id,
                character_id=choice,
                now=now,
                origin="group",
                turn_id=turn_id,
            )
            events.append(GroupEvent("message", round_number, choice, reply.content))
        return GroupRun(group_id=group_id, turn_id=turn_id, events=tuple(events))

    def schedule_proactive(self, job: ProactiveJob) -> None:
        self._require_character(job.character_id)
        self.scheduler.schedule(job)

    def tick(self, *, now: datetime) -> tuple[ChatMessage, ...]:
        generated: list[ChatMessage] = []
        for job in self.scheduler.pop_due(now):
            message = self._reply(
                conversation_id=job.conversation_id,
                character_id=job.character_id,
                now=now,
                origin="proactive",
                turn_id=None,
                prompt=job.prompt,
            )
            generated.append(message)
            self.delivery_ledger.append(
                DeliveryRecord(
                    message_id=message.id,
                    conversation_id=message.conversation_id,
                    origin="proactive",
                    status="queued",
                    attempts=1,
                )
            )
        return tuple(generated)

    def messages(self, conversation_id: str) -> tuple[ChatMessage, ...]:
        return tuple(self._messages.get(conversation_id, ()))

    def _reply(
        self,
        *,
        conversation_id: str,
        character_id: str,
        now: datetime,
        origin: str,
        turn_id: str | None,
        prompt: str | None = None,
    ) -> ChatMessage:
        character = self.characters[character_id]
        history = [message.as_model_message() for message in self._messages.get(conversation_id, ())]
        if prompt is not None:
            history.append({"role": "user", "content": prompt})
        content = self.gateway.complete(
            messages=(
                {
                    "role": "system",
                    "content": f"You are fictional character {character.name} ({character.id}).",
                },
                *history,
            ),
            metadata={
                "shape": self.shape_name,
                "conversation_id": conversation_id,
                "speaker_id": character_id,
                "origin": origin,
            },
        )
        message = ChatMessage(
            id=self._next_id("message"),
            conversation_id=conversation_id,
            sender_id=character_id,
            role="assistant",
            content=content,
            created_at=now,
            origin=origin,
            turn_id=turn_id,
        )
        self._messages.setdefault(conversation_id, []).append(message)
        return message

    def _append_user_message(
        self,
        conversation_id: str,
        content: str,
        now: datetime,
        *,
        origin: str,
        turn_id: str | None = None,
    ) -> None:
        self._messages.setdefault(conversation_id, []).append(
            ChatMessage(
                id=self._next_id("message"),
                conversation_id=conversation_id,
                sender_id="commander",
                role="user",
                content=content,
                created_at=now,
                origin=origin,
                turn_id=turn_id,
            )
        )

    def _require_character(self, character_id: str) -> None:
        if character_id not in self.characters:
            raise KeyError(f"unknown character {character_id!r}")

    def _next_id(self, prefix: str) -> str:
        self._sequence += 1
        return f"{prefix}-{self._sequence:04d}"
