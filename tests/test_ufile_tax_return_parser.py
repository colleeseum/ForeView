# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from services.ufile_tax_return_parser import UFileTaxReturnParser


class FakePage:
    def __init__(self, text: str, values: dict[str, str] | None = None) -> None:
        self._text = text
        self._values = values or {}

    def extract_text(self) -> str:
        return self._text

    def extract_words(self, **_options: object) -> list[dict[str, object]]:
        words: list[dict[str, object]] = []
        for index, (line, amount) in enumerate(self._values.items()):
            top = float(index * 12)
            words.extend(
                (
                    {"text": line, "x0": 400.0, "x1": 440.0, "top": top},
                    {"text": amount, "x0": 500.0, "x1": 560.0, "top": top},
                )
            )
        return words


class FakePdf:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages

    def __enter__(self) -> FakePdf:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class UFileTaxReturnParserTests(unittest.TestCase):
    def test_detects_ufile_pdf_by_extracted_text(self) -> None:
        pages = [FakePage("Tax return Summary\nfor 2024 taxation year")]
        with patch(
            "services.ufile_tax_return_parser.pdfplumber.open",
            return_value=FakePdf(pages),
        ):
            self.assertTrue(UFileTaxReturnParser.detects(b"synthetic pdf"))

    def test_does_not_detect_invalid_pdf(self) -> None:
        with patch(
            "services.ufile_tax_return_parser.pdfplumber.open",
            side_effect=ValueError("not a PDF"),
        ):
            self.assertFalse(UFileTaxReturnParser.detects(b"not a PDF"))

    def test_extracts_primary_taxpayer_summary_by_government_line_number(self) -> None:
        pages = [
            FakePage("Tax return Summary - Combined\nfor 2024 taxation year"),
            FakePage(
                "Taxpayer: Alex Example\nTax return Summary\nfor 2024 taxation year",
                {
                    "10100": "123,45678",
                    "12100": "1,23456",
                    "15000": "124,69134",
                    "20800": "20,00000",
                    "22215": "80000",
                    "30800": "3,20000",
                    "31200": "90000",
                    "31210": "40000",
                    "42000": "18,00000",
                },
            ),
            FakePage("Quebec return\nCPP contribution", {"432": "15,00000"}),
            FakePage("T1-KFS", {"24500": "22,000.00"}),
        ]
        with patch(
            "services.ufile_tax_return_parser.pdfplumber.open",
            return_value=FakePdf(pages),
        ):
            parsed = UFileTaxReturnParser().parse(b"synthetic pdf")

        self.assertEqual(parsed.tax_year, 2024)
        self.assertEqual(parsed.employment_income, Decimal("123456.78"))
        self.assertEqual(parsed.other_employment_income, Decimal("0.00"))
        tax_values = {value.concept: value for value in parsed.tax_values}
        self.assertEqual(
            tax_values["interest_investment_income"].reported_amount,
            Decimal("1234.56"),
        )
        self.assertEqual(tax_values["total_income"].reported_amount, Decimal("124691.34"))
        self.assertEqual(parsed.cpp_qpp, Decimal("4000.00"))
        self.assertEqual(parsed.rrsp_contribution, Decimal("22000.00"))
        self.assertEqual(parsed.rrsp_deduction, Decimal("20000.00"))
        self.assertEqual(parsed.federal_tax, Decimal("18000.00"))
        self.assertEqual(parsed.provincial_tax, Decimal("15000.00"))
        self.assertEqual(parsed.province_of_residence, "QC")
        self.assertEqual(parsed.payroll_plan, "CPP")
        self.assertEqual(parsed.taxpayer_name, "Alex Example")

    def test_rejects_a_package_without_an_individual_summary(self) -> None:
        pages = [FakePage("Tax return Summary - Combined\nfor 2024 taxation year")]
        with (
            patch(
                "services.ufile_tax_return_parser.pdfplumber.open",
                return_value=FakePdf(pages),
            ),
            self.assertRaisesRegex(ValueError, "individual UFile"),
        ):
            UFileTaxReturnParser().parse(b"synthetic pdf")

    def test_finds_name_from_return_body_when_summary_has_no_name_label(self) -> None:
        pages = [
            FakePage(
                "Tax return Summary\nfor 2024 taxation year",
                {"10100": "10000000", "30800": "300000", "42000": "100000"},
            ),
            FakePage("Quebec return", {"432": "100000"}),
            FakePage("2024 Tax return for 2024 prepared for Alex Example by UFile.ca"),
        ]
        with patch(
            "services.ufile_tax_return_parser.pdfplumber.open",
            return_value=FakePdf(pages),
        ):
            parsed = UFileTaxReturnParser().parse(b"synthetic pdf")

        self.assertEqual(parsed.taxpayer_name, "Alex Example")

    def test_finds_name_from_ufile_name_and_birth_date_layout(self) -> None:
        pages = [
            FakePage(
                "Tax return Summary\nfor 2024 taxation year",
                {"10100": "10000000", "30800": "300000", "42000": "100000"},
            ),
            FakePage("Quebec return", {"432": "100000"}),
            FakePage("Name: Alex Example Date of birth: 29-03-1970"),
        ]
        with patch(
            "services.ufile_tax_return_parser.pdfplumber.open",
            return_value=FakePdf(pages),
        ):
            parsed = UFileTaxReturnParser().parse(b"synthetic pdf")

        self.assertEqual(parsed.taxpayer_name, "Alex Example")


if __name__ == "__main__":
    unittest.main()
