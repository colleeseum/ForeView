from __future__ import annotations

import io
import re
from decimal import Decimal
from typing import Any

import pdfplumber

from domain.parsed_ufile_tax_return import ParsedUFileTaxReturn


class UFileTaxReturnParser:
    """Read one taxpayer's factual annual values from a UFile PDF package."""

    _SUMMARY = re.compile(r"Tax return Summary\s+for (\d{4}) taxation year", re.I)
    _NUMBER = re.compile(r"^\(?[\d,]+(?:\.\d{2})?\)?$")

    def parse(self, content: bytes) -> ParsedUFileTaxReturn:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = list(pdf.pages)
            summary_index, tax_year = self._find_individual_summary(pages)
            federal_page = pages[summary_index]
            quebec_page = pages[summary_index + 1] if summary_index + 1 < len(pages) else None
            if quebec_page is None or "Quebec return" not in (quebec_page.extract_text() or ""):
                raise ValueError("The UFile Quebec summary page was not found")

            employment_income = self._required_line(federal_page, "10100")
            other_employment_income = self._optional_line(federal_page, "10400")
            base_cpp_qpp = self._required_line(federal_page, "30800")
            enhanced_cpp_qpp = self._optional_line(federal_page, "22215")
            rrsp_contribution = self._find_rrsp_contribution(pages)

            return ParsedUFileTaxReturn(
                tax_year=tax_year,
                employment_income=employment_income,
                other_employment_income=other_employment_income,
                cpp_qpp=base_cpp_qpp + enhanced_cpp_qpp,
                ei=self._optional_line(federal_page, "31200"),
                qpip=self._optional_line(federal_page, "31210"),
                rrsp_contribution=rrsp_contribution,
                rrsp_deduction=self._optional_line(federal_page, "20800"),
                federal_tax=self._required_line(federal_page, "42000"),
                provincial_tax=self._required_line(quebec_page, "432"),
                province_of_employment="QC",
            )

    def _find_individual_summary(self, pages: list[Any]) -> tuple[int, int]:
        for index, page in enumerate(pages):
            text = page.extract_text() or ""
            match = self._SUMMARY.search(text)
            if match and "Combined" not in text[:200]:
                return index, int(match.group(1))
        raise ValueError("This PDF does not contain an individual UFile tax return summary")

    def _required_line(self, page: Any, line_number: str) -> Decimal:
        value = self._line_amount(page, line_number)
        if value is None:
            raise ValueError(f"UFile line {line_number} was not found")
        return value

    def _optional_line(self, page: Any, line_number: str) -> Decimal:
        return self._line_amount(page, line_number) or Decimal("0.00")

    def _line_amount(
        self, page: Any, line_number: str, *, minimum_x: float = 350
    ) -> Decimal | None:
        words = page.extract_words(use_text_flow=False)
        line_words = [
            word for word in words if word["text"] == line_number and float(word["x0"]) >= minimum_x
        ]
        if not line_words:
            return None
        marker = min(line_words, key=lambda word: float(word["top"]))
        candidates = [
            word
            for word in words
            if abs(float(word["top"]) - float(marker["top"])) < 4
            and float(word["x0"]) >= float(marker["x1"]) - 2
            and self._NUMBER.match(str(word["text"]))
        ]
        if not candidates:
            return None
        return self._amount(str(max(candidates, key=lambda word: float(word["x0"]))["text"]))

    def _find_rrsp_contribution(self, pages: list[Any]) -> Decimal:
        for page in pages:
            value = self._line_amount(page, "24500", minimum_x=0)
            if value is not None:
                return value
        return Decimal("0.00")

    @staticmethod
    def _amount(raw: str) -> Decimal:
        negative = raw.startswith("(") and raw.endswith(")")
        digits = raw.strip("()").replace(",", "")
        if "." not in digits:
            if len(digits) < 3:
                digits = digits.zfill(3)
            digits = f"{digits[:-2]}.{digits[-2:]}"
        value = Decimal(digits)
        return -value if negative else value
