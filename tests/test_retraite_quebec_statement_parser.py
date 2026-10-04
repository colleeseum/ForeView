# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from services.retraite_quebec_statement_parser import RetraiteQuebecStatementParser


class RetraiteQuebecStatementParserTests(unittest.TestCase):
    def test_extracts_combined_earnings_estimates_and_limitation(self) -> None:
        text = """Québec Pension Plan
Statement of Participation
Date of issue: 15 June 2026
MR. ALEX EXAMPLE
Date of birth: 29 March 1970
For now, the estimate only takes
into account the effect of the first component.
Estimate of the amount of your retirement pension (monthly)
1 435 $
863 $
If you continue to make contributions
Age 60 Age 65
1 012 $
738 $
If you stopped making contributions
Age 60 Age 65
Statement of Participation in the Québec Pension Plan
2025 0 $ 81 200 $ 81 200 $ A
2021 26 630 $ 34 863 $ 61 493 $
"""
        with patch.object(RetraiteQuebecStatementParser, "_text", return_value=text):
            result = RetraiteQuebecStatementParser().parse(b"pdf")

        self.assertEqual(result.taxpayer_name, "Alex Example")
        self.assertEqual(result.birth_date, "1970-03-29")
        self.assertTrue(result.excludes_second_enhancement)
        self.assertEqual(result.earnings[0], (2025, Decimal("0"), Decimal("81200"), "A"))
        self.assertEqual(result.estimates[0], ("continue", 60, Decimal("863")))
        self.assertEqual(result.estimates[-1], ("stop", 65, Decimal("1012")))


if __name__ == "__main__":
    unittest.main()
