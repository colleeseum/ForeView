# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Tests for the Hydro-Québec expense-statement detector and parser."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from domain.calver import is_calver
from expense_sources.hydro_qc import HydroQuebecParser, provider
from synthetic_documents import create_synthetic_hydro_qc_statement

STATEMENT_TEXT = """Hydro-Québec
Facture d'électricité du 2 février 2026
SOMMAIRE DE VOTRE FACTURE
Montant de la présente facture
Amount of this bill 31,00 $
Solde précédent 80,00 $
Montant total à payer 111,00 $
DÉTAIL DES COÛTS - TARIF DOMESTIQUE D
Du 31 décembre 2025 au 31 janvier 2026 (31 jours)
"""


def _parser_for(text: str) -> HydroQuebecParser:
    return HydroQuebecParser(lambda _content: [text])


class HydroQuebecParserTest(unittest.TestCase):
    def test_extracts_exact_current_bill_amount_and_service_period(self) -> None:
        parsed = _parser_for(STATEMENT_TEXT).parse(b"pdf")

        self.assertEqual(parsed.suggested_identity, "Hydro")
        self.assertEqual(parsed.amount, Decimal("31.00"))
        self.assertEqual(parsed.period_start, date(2026, 1, 1))
        self.assertEqual(parsed.period_end, date(2026, 1, 31))
        self.assertEqual(parsed.period_kind, "recurring_statement")

    def test_supports_grouped_comma_decimal_amount(self) -> None:
        text = STATEMENT_TEXT.replace("31,00 $", "1 234,56 $")
        self.assertEqual(_parser_for(text).parse(b"pdf").amount, Decimal("1234.56"))

    def test_extracts_amount_when_it_appears_on_french_label(self) -> None:
        text = STATEMENT_TEXT.replace(
            "Montant de la présente facture\nAmount of this bill 31,00 $",
            "Montant de la présente facture 31,00 $\nAmount of this bill",
        )
        self.assertEqual(_parser_for(text).parse(b"pdf").amount, Decimal("31.00"))

    def test_extracts_bilingual_bill_layout(self) -> None:
        english_labels = """Electricity bill of February 2, 2026
DETAILS OF COSTS - DOMESTIC RATE D
From December 31, 2025, to January 31, 2026 (31 days)
"""
        parsed = _parser_for(f"{STATEMENT_TEXT}\n{english_labels}").parse(b"pdf")

        self.assertEqual(parsed.amount, Decimal("31.00"))
        self.assertEqual(parsed.period_start, date(2026, 1, 1))
        self.assertEqual(parsed.period_end, date(2026, 1, 31))

    def test_detects_layout_when_curly_apostrophe_is_removed_by_pdf_extraction(self) -> None:
        text = STATEMENT_TEXT.replace("Facture d'électricité", "Facture delectricité")
        self.assertTrue(_parser_for(text).detects(b"pdf"))

    def test_does_not_substitute_total_due_for_missing_current_bill(self) -> None:
        text = STATEMENT_TEXT.replace("Amount of this bill 31,00 $", "")
        with self.assertRaisesRegex(ValueError, "current Hydro-Québec bill"):
            _parser_for(text).parse(b"pdf")

    def test_rejects_unicode_negative_current_bill_amounts(self) -> None:
        for negative_sign in ("−", "–", "—"):
            with self.subTest(negative_sign=negative_sign):
                text = STATEMENT_TEXT.replace("31,00 $", f"{negative_sign}31,00 $", 1)
                with self.assertRaisesRegex(ValueError, "current Hydro-Québec bill"):
                    _parser_for(text).parse(b"pdf")

    def test_rejects_inconsistent_billed_day_count(self) -> None:
        text = STATEMENT_TEXT.replace("(31 jours)", "(28 jours)")
        with self.assertRaisesRegex(ValueError, "billed-day count"):
            _parser_for(text).parse(b"pdf")

    def test_rejects_bill_with_multiple_service_periods(self) -> None:
        second_contract = """\
DÉTAIL DES COÛTS - TARIF DOMESTIQUE D
Du 15 janvier 2026 au 14 février 2026 (30 jours)
"""

        with self.assertRaisesRegex(ValueError, "multiple service periods"):
            _parser_for(f"{STATEMENT_TEXT}\n{second_contract}").parse(b"pdf")

    def test_rejects_equalized_payments_plan_annual_review(self) -> None:
        for review_text in (
            "RÉVISION ANNUELLE\nSolde MVE",
            "RÉVISION ANNUELLE / ANNUAL REVIEW\nMode de versements égaux",
            "ANNUAL REVIEW\nEPP balance",
        ):
            with self.subTest(review_text=review_text):
                with self.assertRaisesRegex(ValueError, "annual-review bills are not supported"):
                    _parser_for(f"{STATEMENT_TEXT}\n{review_text}").parse(b"pdf")

    def test_does_not_reject_an_ordinary_bill_that_mentions_an_annual_review(self) -> None:
        text = f"{STATEMENT_TEXT}\nYour EPP balance was set at your last annual review."

        self.assertEqual(_parser_for(text).parse(b"pdf").amount, Decimal("31.00"))

    def test_rejects_unrelated_document(self) -> None:
        parser = _parser_for("A generic receipt\nTotal 31,00 $")
        self.assertFalse(parser.detects(b"pdf"))
        with self.assertRaisesRegex(ValueError, "not a supported"):
            parser.parse(b"pdf")

    def test_reads_compressed_synthetic_pdf_through_pdf_extractor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = create_synthetic_hydro_qc_statement(Path(directory) / "hydro.pdf")
            parsed = HydroQuebecParser().parse(path.read_bytes())

        self.assertEqual(parsed.amount, Decimal("31.00"))
        self.assertEqual(parsed.period_start, date(2026, 1, 1))
        self.assertEqual(parsed.period_end, date(2026, 1, 31))

    def test_provider_contract_is_stable(self) -> None:
        source = provider()
        self.assertEqual(source.key, "hydro-quebec")
        self.assertIn("Hydro", source.display_name)
        self.assertTrue(is_calver(source.version))
        self.assertGreater(len(source.help_text), 10)


if __name__ == "__main__":
    unittest.main()
