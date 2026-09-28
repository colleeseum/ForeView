from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScenarioAssumption:
    """One immutable named value attached to a projection scenario."""

    scenario_id: int
    key: str
    value: str
    unit: str | None
