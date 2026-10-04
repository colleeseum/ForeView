# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from projection.salary import (
    PayrollContributionCalculator,
    ProgressiveTaxCalculator,
    QuebecEmploymentTaxCalculator,
)
from projection.tax.rule_values import schedule
from services.public_rule_catalog import PublicRuleCatalog


class SalaryTaxCalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        catalog = PublicRuleCatalog(Path("public_rules"))
        cls.federal = catalog.get("ca-2026-official").rule_set  # type: ignore[union-attr]
        cls.quebec = catalog.get("ca-qc-2026-official").rule_set  # type: ignore[union-attr]
        cls.ontario = catalog.get("ca-on-2026-official").rule_set  # type: ignore[union-attr]

    def test_progressive_tax_applies_each_federal_slice(self) -> None:
        tax = ProgressiveTaxCalculator().calculate(
            Decimal("117045"), schedule(self.federal, "federal_income_tax")
        )

        expected = Decimal("58523") * Decimal("0.14") + Decimal("58522") * Decimal("0.205")
        self.assertEqual(tax, expected)

    def test_cpp_and_qpp_components_match_official_2026_maxima(self) -> None:
        calculator = PayrollContributionCalculator()
        cpp = calculator.calculate(
            Decimal("215600"),
            Decimal("1"),
            "CPP",
            self.ontario,
            self.federal,
            self.quebec,
        )
        qpp = calculator.calculate(
            Decimal("215600"),
            Decimal("1"),
            "QPP",
            self.quebec,
            self.federal,
            self.quebec,
        )

        self.assertEqual(cpp.pension_base, Decimal("3519.45"))
        self.assertEqual(cpp.pension_first_additional, Decimal("711.00"))
        self.assertEqual(cpp.pension_second_additional, Decimal("416.00"))
        self.assertEqual(cpp.ei, Decimal("1123.07"))
        self.assertEqual(qpp.pension_base, Decimal("3768.30"))
        self.assertEqual(qpp.pension_first_additional, Decimal("711.00"))
        self.assertEqual(qpp.ei, Decimal("895.70"))
        self.assertEqual(qpp.qpip, Decimal("442.90"))

    def test_partial_year_prorates_pension_exemption(self) -> None:
        result = PayrollContributionCalculator().calculate(
            Decimal("20000"),
            Decimal("0.5"),
            "QPP",
            self.quebec,
            self.federal,
            self.quebec,
        )

        self.assertEqual(result.pension_base, Decimal("967.25"))
        self.assertEqual(result.pension_first_additional, Decimal("182.50"))

    def test_quebec_resident_with_ontario_employer_uses_cpp_and_regular_ei(self) -> None:
        result = QuebecEmploymentTaxCalculator().calculate(
            employment_income=Decimal("214000"),
            other_employment_income=Decimal("1600"),
            rrsp_contribution=Decimal("31560"),
            rrsp_deduction=Decimal("31560"),
            employment_fraction=Decimal("1"),
            payroll_plan="CPP",
            federal_rules=self.federal,
            quebec_rules=self.quebec,
            payroll_rules=self.ontario,
        )

        self.assertEqual(result.gross_income, Decimal("215600.00"))
        self.assertEqual(result.taxable_federal_income, Decimal("182913.00"))
        self.assertEqual(result.taxable_quebec_income, Decimal("181463.00"))
        self.assertEqual(result.federal_tax, Decimal("28506.12"))
        self.assertEqual(result.quebec_tax, Decimal("33607.91"))
        self.assertEqual(result.net_income_after_tax, Decimal("147273.55"))
        self.assertEqual(result.disposable_income, Decimal("115713.55"))

    def test_rrsp_cash_and_deduction_have_distinct_effects(self) -> None:
        common = dict(
            employment_income=Decimal("100000"),
            other_employment_income=Decimal("0"),
            employment_fraction=Decimal("1"),
            payroll_plan="QPP",
            federal_rules=self.federal,
            quebec_rules=self.quebec,
            payroll_rules=self.quebec,
        )
        undeducted = QuebecEmploymentTaxCalculator().calculate(
            **common,
            rrsp_contribution=Decimal("10000"),
            rrsp_deduction=Decimal("0"),
        )
        deducted = QuebecEmploymentTaxCalculator().calculate(
            **common,
            rrsp_contribution=Decimal("10000"),
            rrsp_deduction=Decimal("10000"),
        )

        self.assertEqual(undeducted.taxable_federal_income - deducted.taxable_federal_income, 10000)
        self.assertEqual(undeducted.rrsp_contribution, deducted.rrsp_contribution)
        self.assertGreater(undeducted.federal_tax, deducted.federal_tax)
        self.assertGreater(undeducted.quebec_tax, deducted.quebec_tax)


if __name__ == "__main__":
    unittest.main()
