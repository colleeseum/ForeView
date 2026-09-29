from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from projection.public_rules import PublicRuleSet
from projection.tax.rule_values import parameter

from .payroll_contributions import PayrollContributions

_CENT = Decimal("0.01")


class PayrollContributionCalculator:
    """Calculate annual CPP/QPP, EI and Quebec-resident QPIP amounts."""

    def calculate(
        self,
        employment_income: Decimal,
        employment_fraction: Decimal,
        payroll_plan: str,
        payroll_rules: PublicRuleSet,
        federal_rules: PublicRuleSet,
        quebec_rules: PublicRuleSet,
    ) -> PayrollContributions:
        plan = payroll_plan.upper()
        if plan not in {"CPP", "QPP"}:
            raise ValueError("Payroll plan must be CPP or QPP")
        if not Decimal("0") <= employment_fraction <= Decimal("1"):
            raise ValueError("Employment fraction must be between zero and one")
        income = max(employment_income, Decimal("0"))
        prefix = plan.lower()
        exemption = parameter(payroll_rules, f"{prefix}_basic_exemption") * employment_fraction
        ympe = parameter(payroll_rules, f"{prefix}_ympe")
        yampe = parameter(payroll_rules, f"{prefix}_yampe")
        first_rate = parameter(payroll_rules, f"{prefix}_employee_rate_first")
        base_rate = (
            parameter(quebec_rules, "qpp_employee_rate_base")
            if plan == "QPP"
            else parameter(federal_rules, "cpp_employee_rate_base")
        )
        first_additional_rate = first_rate - base_rate
        first_earnings = min(max(income - exemption, Decimal("0")), ympe - exemption)
        second_earnings = min(max(income - ympe, Decimal("0")), yampe - ympe)
        base = self._money(first_earnings * base_rate)
        first_additional = self._money(first_earnings * first_additional_rate)
        second_additional = self._money(
            second_earnings * parameter(payroll_rules, f"{prefix}_employee_rate_second")
        )
        ei = self._money(
            min(
                income * parameter(payroll_rules, "ei_employee_rate"),
                parameter(payroll_rules, "ei_employee_max_premium"),
            )
        )
        qpip = self._money(
            min(
                income * parameter(quebec_rules, "qpip_employee_rate"),
                parameter(quebec_rules, "qpip_employee_max_premium"),
            )
        )
        return PayrollContributions(base, first_additional, second_additional, ei, qpip)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(_CENT, rounding=ROUND_HALF_UP)
