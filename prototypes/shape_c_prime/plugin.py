"""C' prototype: an AstrBot-shaped adapter feeds a director plugin."""

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
    SKIP_TOKEN,
)
from prototypes.shared.model_gateway import ModelGateway
from prototypes.shared.scheduler import ProactiveJob
from .astrbot_shim import AstrBotRuntime, JuusPlatformAdapter, PlatformEvent, ScheduledHostJob


class JuusAstrBotPlugin:
    """Director plugin with host-owned transport and timer seams."""

    shape_name = "C-prime-astrbot-plugin"

    def __init__(
        self,
        *,
        runtime: AstrBotRuntime,
        characters: Sequence[Character],
        groups: Sequence[Group],
        gateway: ModelGateway,
        director: ScriptedDirector,
    ) -> None:
        self.runtime = runtime
        self.characters = {character.id: character for character in characters}
        self.groups = {group.id: group for group in groups}
        self.gateway = gateway
        self.director = director
        self.adapter = JuusPlatformAdapter(runtime, self.handle_event)
        runtime.install_adapter(self.adapter)
        self._messages: dict[str, list[ChatMessage]] = {}
        self._sequence = 0
        self.delivery_ledger: list[DeliveryRecord] = []
        self.events: list[GroupEvent] = []

    def handle_event(self, event: PlatformEvent) -> None:
        if event.group_id is None:
            self._handle_single(event)
        else:
            self._handle_group(event)

    def schedule_proactive(self, job: ProactiveJob) -> None:
        self._require_character(job.character_id)
        self.runtime.schedule_once(
            ScheduledHostJob(job.id, job.due_at, self._handle_proactive, job)
        )

    def messages(self, conversation_id: str) -> tuple[ChatMessage, ...]:
        return tuple(self._messages.get(conversation_id, ()))

    def _handle_single(self, event: PlatformEvent) -> None:
        conversation_id = f"dm:{event.sender_id}:{event.channel_id}"
        self._append_user(conversation_id, event.text, event.created_at, origin="single")
        reply = self._reply(
            conversation_id=conversation_id,
            character_id=event.target_character_id or self._default_character_id,
            now=event.created_at,
            origin="single",
            turn_id=None,
        )
        self.runtime.send_text(
            channel_id=event.channel_id,
            sender_id=reply.sender_id,
            text=reply.content,
            origin=reply.origin,
        )

    def _handle_group(self, event: PlatformEvent) -> None:
        group = self.groups[event.group_id or ""]
        conversation_id = f"group:{group.id}"
        turn_id = self._next_id("turn")
        self._append_user(conversation_id, event.text, event.created_at, origin="group", turn_id=turn_id)
        for round_number in range(1, group.max_rounds + 1):
            choice = self.director.choose(
                group_id=group.id,
                member_ids=group.member_ids,
                history=tuple(self._messages[conversation_id]),
                round_number=round_number,
            )
            event_record = GroupEvent("decision", round_number, choice, choice)
            self.events.append(event_record)
            if choice == SKIP_TOKEN:
                self.events.append(GroupEvent("skip", round_number, None, SKIP_TOKEN))
                continue
            reply = self._reply(
                conversation_id=conversation_id,
                character_id=choice,
                now=event.created_at,
                origin="group",
                turn_id=turn_id,
            )
            self.events.append(GroupEvent("message", round_number, choice, reply.content))
            self.runtime.send_text(
                channel_id=event.channel_id,
                sender_id=reply.sender_id,
                text=reply.content,
                origin=reply.origin,
            )

    def _handle_proactive(self, job: ProactiveJob) -> None:
        message = self._reply(
            conversation_id=job.conversation_id,
            character_id=job.character_id,
            now=job.due_at,
            origin="proactive",
            turn_id=None,
            prompt=job.prompt,
        )
        self.runtime.send_text(
            channel_id=job.conversation_id,
            sender_id=message.sender_id,
            text=message.content,
            origin=message.origin,
        )
        self.delivery_ledger.append(
            DeliveryRecord(
                message_id=message.id,
                conversation_id=message.conversation_id,
                origin="proactive",
                status="queued",
                attempts=1,
            )
        )

    @property
    def _default_character_id(self) -> str:
        return next(iter(self.characters))

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

    def _append_user(
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
