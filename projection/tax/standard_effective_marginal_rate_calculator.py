# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Combined marginal rates for jurisdictions without additional rate mechanisms."""

from __future__ import annotations

from decimal import Decimal

from projection.public_rules import PublicRuleSet

from .effective_marginal_rate import EffectiveMarginalRate
from .federal_marginal_rate_model import FederalMarginalRateModel, bracket_rate
from .schedule_builder import build_schedule


class StandardEffectiveMarginalRateCalculator:
    def __init__(self, jurisdiction: str) -> None:
        self.jurisdiction = jurisdiction

    def calculate(
        self, federal: PublicRuleSet, provincial: PublicRuleSet
    ) -> tuple[EffectiveMarginalRate, ...]:
        if len(provincial.tax_brackets) != 1:
            raise ValueError(
                f"Expected one tax schedule in {provincial.rule_set_id}, "
                f"found {len(provincial.tax_brackets)}"
            )
        federal_model = FederalMarginalRateModel(federal)
        provincial_schedule = provincial.tax_brackets[0]
        breakpoints = (
            *federal_model.breakpoints,
            *(item.upper_bound for item in provincial_schedule.brackets if item.upper_bound),
        )

        def rate_at(income: Decimal) -> Decimal:
            return federal_model.rate_at(income) + bracket_rate(provincial_schedule, income)

        return build_schedule(breakpoints, rate_at)
