# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from services.cra_notice_parser import CraNoticeParser
from services.revenu_quebec_notice_parser import RevenuQuebecNoticeParser


class TaxNoticeParserTests(unittest.TestCase):
    def test_cra_notice_extracts_assessment_and_next_year_rrsp_room(self) -> None:
        text = """Notice of assessment
Net federal tax
Tax year 2025
Date issued May 11, 2026
ALEX EXAMPLE
1 SAMPLE STREET
15000 Total income 223,074
23600 Net income 214,510
26000 Taxable income 214,510
35000 Total non-refundable tax credits 3,121
42000 Net federal tax 43,995.95
43500 Total payable 43,995.95
43700 Total income tax deducted 47,010.24
44000 Refundable Quebec abatement 7,259.33
48200 Total credits 54,269.57
Balance from this assessment 10,273.62 CR
Your Canada training credit limit for next year is $250.00.
RRSP deduction limit for 2025 32,490
Minus: Employer's PRPP contributions for 2025 0
Minus: Allowable RRSP contributions deducted for 2025 7,490
Equals: Your unused RRSP deduction room at the end of 2025 25,000
18% of 2025 earned income, up to a maximum 33,810
Minus: 2025 pension adjustment (PA) 0
Minus: 2025 prescribed amount for connected persons 0
Equals: Additional RRSP deduction limit you earned in 2025 (if negative, will be "0") 33,810
Your 2026 RRSP deduction limit
Minus: 2026 net past service pension adjustment (PSPA) 0
Plus: 2026 pension adjustment reversal (PAR) 0
Equals:RRSP deduction limit for2026 58,810
Minus: Unused RRSP contributions previously reported and available to deduct for 2026 0
Your available RRSP contribution room for2026 58,810
"""
        with patch.object(CraNoticeParser, "_text", return_value=text):
            result = CraNoticeParser().parse(b"pdf")

        self.assertEqual(result.jurisdiction, "CA")
        self.assertEqual(result.taxpayer_name, "Alex Example")
        self.assertEqual(result.net_tax, Decimal("43995.95"))
        self.assertEqual(result.balance, Decimal("-10273.62"))
        self.assertEqual(result.rrsp_effective_year, 2026)
        self.assertEqual(result.rrsp_available_room, Decimal("58810"))
        concepts = {value.concept for value in result.tax_values}
        self.assertIn("canada_training_credit_limit", concepts)
        self.assertIn("rrsp_pension_adjustment", concepts)

    def test_revenu_quebec_notice_keeps_qpip_and_withholding_out_of_tax(self) -> None:
        text = """Revenu Québec
Notice of assessment
2025 taxation year
Date of notice: May 12, 2026
199 Total income = 223,074.07 223,074.07
130 Interest and other investment income + 3,900.00 3,925.26
275 Net income = 213,090.07 213,090.07
299 Taxable income = 213,090.07 213,090.07
432 Income tax = 42,015.43 42,015.43
439 QPIP premium on income from self-employment or
employment outside Québec + 267.31 267.31
454 Transferable portion of the income tax withheld for
another province - 38,462.92 38,462.92
Balance due for this notice of assessment = $3,827.89
First name and last name Date of notice Identification number Taxation year
Alex Example May 12, 2026 123 2025
"""
        with patch.object(RevenuQuebecNoticeParser, "_text", return_value=text):
            result = RevenuQuebecNoticeParser().parse(b"pdf")

        self.assertEqual(result.jurisdiction, "CA-QC")
        self.assertEqual(result.taxpayer_name, "Alex Example")
        self.assertEqual(result.net_tax, Decimal("42015.43"))
        self.assertEqual(result.additional_contributions, Decimal("267.31"))
        self.assertEqual(result.tax_withheld, Decimal("38462.92"))
        interest = next(
            value for value in result.tax_values if value.concept == "interest_investment_income"
        )
        self.assertEqual(interest.reported_amount, Decimal("3900.00"))
        self.assertEqual(interest.determined_amount, Decimal("3925.26"))


if __name__ == "__main__":
    unittest.main()
