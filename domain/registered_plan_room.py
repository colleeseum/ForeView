from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RegisteredPlanRoom:
    """Official contribution-room snapshot for one person and plan."""

    id: int
    person_id: int
    plan_type: str
    effective_year: int
    as_of_date: str
    deduction_limit: Decimal
    unused_deduction_room: Decimal
    new_room: Decimal
    unused_contributions: Decimal
    available_room: Decimal
    source: str
    source_version: str
