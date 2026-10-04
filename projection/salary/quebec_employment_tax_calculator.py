# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from projection.public_rules import PublicRuleSet
from projection.tax.rule_values import parameter, schedule

from .employment_tax_estimate import EmploymentTaxEstimate
from .payroll_contribution_calculator import PayrollContributionCalculator
from .payroll_contributions import PayrollContributions
from .progressive_tax_calculator import ProgressiveTaxCalculator

_CENT = Decimal("0.01")


class QuebecEmploymentTaxCalculator:
    """Estimate annual federal and Quebec tax for supported employment income."""

    def __init__(self) -> None:
        self._progressive = ProgressiveTaxCalculator()
        self._payroll = PayrollContributionCalculator()

    def calculate(
        self,
        *,
        employment_income: Decimal,
        other_employment_income: Decimal,
        rrsp_contribution: Decimal,
        rrsp_deduction: Decimal,
        employment_fraction: Decimal,
        payroll_plan: str,
        federal_rules: PublicRuleSet,
        quebec_rules: PublicRuleSet,
        payroll_rules: PublicRuleSet,
    ) -> EmploymentTaxEstimate:
        values = (
            employment_income,
            other_employment_income,
            rrsp_contribution,
            rrsp_deduction,
        )
        if any(value < 0 for value in values):
            raise ValueError("Employment projection amounts cannot be negative")
        gross = employment_income + other_employment_income
        payroll = self._payroll.calculate(
            gross,
            employment_fraction,
            payroll_plan,
            payroll_rules,
            federal_rules,
            quebec_rules,
        )
        federal_taxable = max(gross - rrsp_deduction - payroll.pension_deduction, Decimal("0"))
        worker_deduction = min(
            employment_income * parameter(quebec_rules, "quebec_worker_deduction_rate"),
            parameter(quebec_rules, "quebec_worker_deduction_max"),
        )
        quebec_taxable = max(
            federal_taxable - worker_deduction,
            Decimal("0"),
        )
        federal_tax = self._federal_tax(
            federal_taxable, gross, payroll, federal_rules, quebec_rules
        )
        quebec_tax = self._quebec_tax(quebec_taxable, quebec_rules)
        return EmploymentTaxEstimate(
            gross_income=self._money(gross),
            taxable_federal_income=self._money(federal_taxable),
            taxable_quebec_income=self._money(quebec_taxable),
            payroll=payroll,
            federal_tax=self._money(federal_tax),
            quebec_tax=self._money(quebec_tax),
            rrsp_contribution=self._money(rrsp_contribution),
            rrsp_deduction=self._money(rrsp_deduction),
            rule_year=federal_rules.tax_year,
        )

    def _federal_tax(
        self,
        taxable_income: Decimal,
        employment_income: Decimal,
        payroll: PayrollContributions,
        federal_rules: PublicRuleSet,
        quebec_rules: PublicRuleSet,
    ) -> Decimal:
        federal_schedule = schedule(federal_rules, "federal_income_tax")
        bracket_tax = self._progressive.calculate(taxable_income, federal_schedule)
        bpa = self._federal_basic_personal_amount(taxable_income, federal_rules)
        employment_amount = min(
            employment_income, parameter(federal_rules, "canada_employment_amount")
        )
        credit_base = bpa + payroll.pension_base + payroll.ei + payroll.qpip + employment_amount
        credits = credit_base * federal_schedule.brackets[0].rate
        basic_federal_tax = max(bracket_tax - credits, Decimal("0"))
        abatement = parameter(quebec_rules, "quebec_federal_tax_abatement_rate")
        return basic_federal_tax * (Decimal("1") - abatement)

    def _quebec_tax(self, taxable_income: Decimal, rules: PublicRuleSet) -> Decimal:
        quebec_schedule = schedule(rules, "quebec_income_tax")
        bracket_tax = self._progressive.calculate(taxable_income, quebec_schedule)
        credit = parameter(rules, "quebec_basic_personal_amount") * quebec_schedule.brackets[0].rate
        return max(bracket_tax - credit, Decimal("0"))

    @staticmethod
    def _federal_basic_personal_amount(net_income: Decimal, rules: PublicRuleSet) -> Decimal:
        maximum = parameter(rules, "federal_basic_personal_amount_max")
        minimum = parameter(rules, "federal_basic_personal_amount_min")
        brackets = schedule(rules, "federal_income_tax").brackets
        phaseout_start = brackets[-3].upper_bound
        phaseout_end = brackets[-2].upper_bound
        if phaseout_start is None or phaseout_end is None:
            raise ValueError("Federal schedule lacks BPA phaseout thresholds")
        if net_income <= phaseout_start:
            return maximum
        if net_income >= phaseout_end:
            return minimum
        reduction = (
            (maximum - minimum) * (net_income - phaseout_start) / (phaseout_end - phaseout_start)
        )
        return maximum - reduction

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(_CENT, rounding=ROUND_HALF_UP)
