"""In-memory timer primitive for the M0 proactive-message trial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProactiveJob:
    id: str
    due_at: datetime
    character_id: str
    conversation_id: str
    prompt: str


class InMemoryScheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, ProactiveJob] = {}

    def schedule(self, job: ProactiveJob) -> None:
        if job.id in self._jobs:
            raise ValueError(f"duplicate proactive job {job.id}")
        self._jobs[job.id] = job

    def pop_due(self, now: datetime) -> tuple[ProactiveJob, ...]:
        due = sorted(
            (job for job in self._jobs.values() if job.due_at <= now),
            key=lambda job: (job.due_at, job.id),
        )
        for job in due:
            del self._jobs[job.id]
        return tuple(due)

    @property
    def pending_count(self) -> int:
        return len(self._jobs)
