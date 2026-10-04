# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class HouseholdExpensePlan:
    """Scenario-level after-tax household spending assumptions."""

    scenario_id: int
    start_year: int
    required_annual_amount: Decimal
    required_annual_growth: Decimal
    discretionary_annual_amount: Decimal
    discretionary_annual_growth: Decimal

    def required_for_year(self, year: int) -> Decimal:
        return self._grown(self.required_annual_amount, self.required_annual_growth, year)

    def discretionary_for_year(self, year: int) -> Decimal:
        return self._grown(self.discretionary_annual_amount, self.discretionary_annual_growth, year)

    def total_for_year(self, year: int) -> Decimal:
        return self.required_for_year(year) + self.discretionary_for_year(year)

    def _grown(self, amount: Decimal, growth: Decimal, year: int) -> Decimal:
        years = max(0, year - self.start_year)
        return (amount * (Decimal("1") + growth) ** years).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
