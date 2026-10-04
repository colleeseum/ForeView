# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Manitoba effective marginal rate including its income-tested BPA."""

from __future__ import annotations

from decimal import Decimal

from projection.public_rules import PublicRuleSet

from .effective_marginal_rate import EffectiveMarginalRate
from .federal_marginal_rate_model import FederalMarginalRateModel, bracket_rate
from .rule_values import parameter
from .schedule_builder import build_schedule


class ManitobaEffectiveMarginalRateCalculator:
    jurisdiction = "CA-MB"

    def calculate(
        self, federal: PublicRuleSet, provincial: PublicRuleSet
    ) -> tuple[EffectiveMarginalRate, ...]:
        if len(provincial.tax_brackets) != 1:
            raise ValueError(f"Expected one Manitoba tax schedule in {provincial.rule_set_id}")
        federal_model = FederalMarginalRateModel(federal)
        provincial_schedule = provincial.tax_brackets[0]
        basic_amount = parameter(provincial, "manitoba_basic_personal_amount")
        phaseout_start = parameter(provincial, "manitoba_bpa_phaseout_start")
        phaseout_end = parameter(provincial, "manitoba_bpa_phaseout_end")
        bpa_marginal_rate = (
            basic_amount / (phaseout_end - phaseout_start) * provincial_schedule.brackets[0].rate
        )
        breakpoints = (
            *federal_model.breakpoints,
            *(item.upper_bound for item in provincial_schedule.brackets if item.upper_bound),
            phaseout_start,
            phaseout_end,
        )

        def rate_at(income: Decimal) -> Decimal:
            rate = federal_model.rate_at(income) + bracket_rate(provincial_schedule, income)
            if phaseout_start < income <= phaseout_end:
                rate += bpa_marginal_rate
            return rate

        return build_schedule(breakpoints, rate_at)
