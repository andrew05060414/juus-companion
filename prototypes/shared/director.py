"""Deterministic director used to make the spike repeatable."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .domain import ChatMessage, SKIP_TOKEN


class ScriptedDirector:
    """Return a planned speaker or ``[SKIP]`` for each group round.

    A real director can replace this object without changing the service or
    AstrBot boundary. The script makes the acceptance run deterministic and
    exercises both speaking and no-op decisions.
    """

    def __init__(self, scripts: Mapping[str, Sequence[str]]) -> None:
        self._scripts = {group_id: tuple(script) for group_id, script in scripts.items()}
        self._positions: dict[str, int] = {}

    def choose(
        self,
        *,
        group_id: str,
        member_ids: Sequence[str],
        history: Sequence[ChatMessage],
        round_number: int,
    ) -> str:
        del history, round_number
        script = self._scripts.get(group_id, ())
        position = self._positions.get(group_id, 0)
        self._positions[group_id] = position + 1
        choice = script[position] if position < len(script) else SKIP_TOKEN
        if choice != SKIP_TOKEN and choice not in member_ids:
            raise ValueError(f"director selected non-member {choice!r}")
        return choice
