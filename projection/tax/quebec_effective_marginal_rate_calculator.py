"""Quebec effective marginal ordinary-income rate calculator."""

from __future__ import annotations

from decimal import Decimal

from projection.public_rules import PublicRuleSet

from .effective_marginal_rate import EffectiveMarginalRate
from .federal_marginal_rate_model import FederalMarginalRateModel, bracket_rate
from .rule_values import parameter, schedule
from .schedule_builder import build_schedule


class QuebecEffectiveMarginalRateCalculator:
    jurisdiction = "CA-QC"

    def calculate(
        self, federal: PublicRuleSet, provincial: PublicRuleSet
    ) -> tuple[EffectiveMarginalRate, ...]:
        federal_model = FederalMarginalRateModel(federal)
        provincial_schedule = schedule(provincial, "quebec_income_tax")
        abatement = parameter(provincial, "quebec_federal_tax_abatement_rate")
        breakpoints = (
            *federal_model.breakpoints,
            *(item.upper_bound for item in provincial_schedule.brackets if item.upper_bound),
        )

        def rate_at(income: Decimal) -> Decimal:
            return federal_model.rate_at(income) * (Decimal("1") - abatement) + bracket_rate(
                provincial_schedule, income
            )

        return build_schedule(breakpoints, rate_at)
