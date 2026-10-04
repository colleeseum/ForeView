from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EmploymentProjectionSettings:
    """Recurring scenario assumptions for one person's employment."""

    scenario_id: int
    person_id: int
    default_raise: Decimal
    retirement_date: str | None
    recurring_rrsp_contribution: Decimal
    recurring_rrsp_deduction: Decimal
    recurring_other_income: Decimal
