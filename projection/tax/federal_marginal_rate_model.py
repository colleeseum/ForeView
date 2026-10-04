# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Federal marginal-rate behavior shared by provincial calculators."""

from __future__ import annotations

from decimal import Decimal

from projection.public_rules import PublicRuleSet, TaxBracketSchedule

from .rule_values import parameter, schedule


class FederalMarginalRateModel:
    def __init__(self, rule_set: PublicRuleSet) -> None:
        self.schedule: TaxBracketSchedule = schedule(rule_set, "federal_income_tax")
        self._bpa_max = parameter(rule_set, "federal_basic_personal_amount_max")
        self._bpa_min = parameter(rule_set, "federal_basic_personal_amount_min")
        bounded = [item.upper_bound for item in self.schedule.brackets if item.upper_bound]
        if len(bounded) != 4:
            raise ValueError("Federal BPA phaseout requires the five-bracket federal schedule")
        self.phaseout_start = bounded[2]
        self.phaseout_end = bounded[3]

    @property
    def breakpoints(self) -> tuple[Decimal, ...]:
        return tuple(
            item.upper_bound for item in self.schedule.brackets if item.upper_bound is not None
        )

    def rate_at(self, income: Decimal) -> Decimal:
        rate = _bracket_rate(self.schedule, income)
        if self.phaseout_start < income <= self.phaseout_end:
            bpa_reduction = (self._bpa_max - self._bpa_min) / (
                self.phaseout_end - self.phaseout_start
            )
            rate += bpa_reduction * self.schedule.brackets[0].rate
        return rate


def bracket_rate(schedule: TaxBracketSchedule, income: Decimal) -> Decimal:
    return _bracket_rate(schedule, income)


def _bracket_rate(schedule: TaxBracketSchedule, income: Decimal) -> Decimal:
    for bracket in schedule.brackets:
        if bracket.upper_bound is None or income <= bracket.upper_bound:
            return bracket.rate
    raise AssertionError("Validated schedules always have an open-ended final bracket")
