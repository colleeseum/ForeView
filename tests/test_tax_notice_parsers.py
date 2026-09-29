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
42000 Net federal tax 43,995.95
43700 Total income tax deducted 47,010.24
Balance from this assessment 10,273.62 CR
Equals: Your unused RRSP deduction room at the end of 2025 25,000
Equals: Additional RRSP deduction limit you earned in 2025 (if negative, will be "0") 33,810
Your 2026 RRSP deduction limit
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

    def test_revenu_quebec_notice_keeps_qpip_and_withholding_out_of_tax(self) -> None:
        text = """Revenu Québec
Notice of assessment
2025 taxation year
Date of notice: May 12, 2026
199 Total income = 223,074.07 223,074.07
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


if __name__ == "__main__":
    unittest.main()
