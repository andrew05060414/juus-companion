"""A tiny local AstrBot-shaped host for the C' acceptance trial.

It intentionally models only the platform registration, inbound event, outbound
send, and scheduled-job seams needed by this spike. It never connects to the
NAS AstrBot instance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any


PLATFORM_ADAPTER_REGISTRY: dict[str, type[Any]] = {}


def register_platform_adapter(
    name: str,
    description: str,
    *,
    default_config_tmpl: dict[str, Any] | None = None,
) -> Callable[[type[Any]], type[Any]]:
    """Mirror AstrBot's decorator registration seam for local testing."""

    def decorator(adapter_type: type[Any]) -> type[Any]:
        adapter_type.platform_name = name
        adapter_type.platform_description = description
        adapter_type.default_config_tmpl = default_config_tmpl or {}
        PLATFORM_ADAPTER_REGISTRY[name] = adapter_type
        return adapter_type

    return decorator


@dataclass(frozen=True)
class PlatformEvent:
    message_id: str
    channel_id: str
    sender_id: str
    text: str
    created_at: datetime
    group_id: str | None = None
    target_character_id: str | None = None


@dataclass(frozen=True)
class OutboundMessage:
    channel_id: str
    sender_id: str
    text: str
    origin: str


@dataclass(frozen=True)
class ScheduledHostJob:
    id: str
    due_at: datetime
    callback: Callable[[Any], None]
    payload: Any


class AstrBotRuntime:
    """Local host that records the seams a plugin would call."""

    def __init__(self) -> None:
        self.adapters: dict[str, JuusPlatformAdapter] = {}
        self.outbox: list[OutboundMessage] = []
        self._jobs: dict[str, ScheduledHostJob] = {}

    def install_adapter(self, adapter: JuusPlatformAdapter) -> None:
        self.adapters[adapter.platform_name] = adapter

    def send_text(self, *, channel_id: str, sender_id: str, text: str, origin: str) -> None:
        self.outbox.append(OutboundMessage(channel_id, sender_id, text, origin))

    def schedule_once(self, job: ScheduledHostJob) -> None:
        if job.id in self._jobs:
            raise ValueError(f"duplicate host job {job.id}")
        self._jobs[job.id] = job

    def receive(self, event: PlatformEvent) -> None:
        if not self.adapters:
            raise RuntimeError("no platform adapter installed")
        next(iter(self.adapters.values())).receive(event)

    def run_due(self, now: datetime) -> None:
        due = sorted(
            (job for job in self._jobs.values() if job.due_at <= now),
            key=lambda job: (job.due_at, job.id),
        )
        for job in due:
            del self._jobs[job.id]
            job.callback(job.payload)


@register_platform_adapter(
    "juus-local",
    "Juus local test platform adapter",
    default_config_tmpl={"mode": "local-only"},
)
class JuusPlatformAdapter:
    """Translate local platform events into the plugin callback."""

    platform_name = "juus-local"

    def __init__(self, runtime: AstrBotRuntime, on_event: Callable[[PlatformEvent], None]) -> None:
        self.runtime = runtime
        self.on_event = on_event

    def receive(self, event: PlatformEvent) -> None:
        self.on_event(event)
