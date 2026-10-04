# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Ontario effective marginal ordinary-income rate calculator."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from projection.public_rules import PublicRuleSet, TaxBracketSchedule

from .effective_marginal_rate import EffectiveMarginalRate
from .federal_marginal_rate_model import FederalMarginalRateModel, bracket_rate
from .rule_values import parameter, schedule
from .schedule_builder import build_schedule


class OntarioEffectiveMarginalRateCalculator:
    jurisdiction = "CA-ON"

    def calculate(
        self, federal: PublicRuleSet, provincial: PublicRuleSet
    ) -> tuple[EffectiveMarginalRate, ...]:
        federal_model = FederalMarginalRateModel(federal)
        provincial_schedule = schedule(provincial, "ontario_income_tax")
        basic_amount = parameter(provincial, "ontario_basic_personal_amount")
        first_threshold = parameter(provincial, "ontario_surtax_threshold_first")
        first_rate = parameter(provincial, "ontario_surtax_rate_first")
        second_threshold = parameter(provincial, "ontario_surtax_threshold_second")
        second_rate = parameter(provincial, "ontario_surtax_rate_second")
        credit = basic_amount * provincial_schedule.brackets[0].rate
        first_income = self._income_for_basic_tax(
            provincial_schedule, first_threshold + credit
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        second_income = self._income_for_basic_tax(
            provincial_schedule, second_threshold + credit
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        breakpoints = (
            *federal_model.breakpoints,
            *(item.upper_bound for item in provincial_schedule.brackets if item.upper_bound),
            first_income,
            second_income,
        )

        def rate_at(income: Decimal) -> Decimal:
            provincial_rate = bracket_rate(provincial_schedule, income)
            if income > second_income:
                provincial_rate *= Decimal("1") + first_rate + second_rate
            elif income > first_income:
                provincial_rate *= Decimal("1") + first_rate
            return federal_model.rate_at(income) + provincial_rate

        return build_schedule(breakpoints, rate_at)

    @staticmethod
    def _income_for_basic_tax(schedule: TaxBracketSchedule, target_tax: Decimal) -> Decimal:
        lower = Decimal("0")
        accumulated = Decimal("0")
        for bracket in schedule.brackets:
            if bracket.upper_bound is None:
                return lower + (target_tax - accumulated) / bracket.rate
            width = bracket.upper_bound - lower
            bracket_tax = width * bracket.rate
            if accumulated + bracket_tax >= target_tax:
                return lower + (target_tax - accumulated) / bracket.rate
            accumulated += bracket_tax
            lower = bracket.upper_bound
        raise AssertionError("Validated schedules always have an open-ended final bracket")
