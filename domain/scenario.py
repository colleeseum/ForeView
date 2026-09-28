from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scenario:
    """One immutable projection scenario definition."""

    id: int
    name: str
    baseline_date: str
    description: str | None
