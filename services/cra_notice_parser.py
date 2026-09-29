from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from domain.parsed_tax_assessment import ParsedTaxAssessment


class CraNoticeParser:
    """Extract assessed federal totals and RRSP room from a CRA notice."""

    @staticmethod
    def detects(content: bytes) -> bool:
        try:
            text = CraNoticeParser._text(content)
        except (OSError, ValueError, PdfminerException):
            return False
        return "Notice of assessment" in text and "Net federal tax" in text

    def parse(self, content: bytes) -> ParsedTaxAssessment:
        text = self._text(content)
        year = int(self._required(text, r"Tax year\s+(\d{4})", "tax year"))
        issued = (
            datetime.strptime(
                self._required(text, r"Date issued\s+([A-Z][a-z]+ \d{1,2}, \d{4})", "issue date"),
                "%B %d, %Y",
            )
            .date()
            .isoformat()
        )
        room_year = self._optional_int(text, r"Your (\d{4}) RRSP deduction limit")
        balance_value = self._required(
            text, r"Balance from this assessment\s+([\d,]+(?:\.\d{2})?)\s*(CR|DR)?", "balance"
        )
        balance_match = re.search(
            r"Balance from this assessment\s+([\d,]+(?:\.\d{2})?)\s*(CR|DR)?", text
        )
        balance = self._amount(balance_value)
        if balance_match and balance_match.group(2) == "CR":
            balance = -balance
        return ParsedTaxAssessment(
            tax_year=year,
            jurisdiction="CA",
            issued_on=issued,
            taxpayer_name=self._taxpayer_name(text),
            total_income=self._line(text, "15000", "Total income"),
            net_income=self._line(text, "23600", "Net income"),
            taxable_income=self._line(text, "26000", "Taxable income"),
            net_tax=self._line(text, "42000", "Net federal tax"),
            additional_contributions=Decimal("0"),
            tax_withheld=self._line(text, "43700", "Total income tax deducted"),
            balance=balance,
            rrsp_effective_year=room_year,
            rrsp_deduction_limit=self._optional_amount(
                text,
                rf"Equals:\s*RRSP deduction limit for\s*{room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
            ),
            rrsp_unused_deduction_room=self._optional_amount(
                text, rf"unused RRSP deduction room at the end of {year}\s+([\d,]+)"
            ),
            rrsp_new_room=self._optional_amount(
                text, rf"Additional RRSP deduction limit you earned in {year}.*?\s+([\d,]+)\s*$"
            ),
            rrsp_unused_contributions=self._optional_amount(
                text,
                rf"Unused RRSP contributions previously reported and available to deduct for {room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
            ),
            rrsp_available_room=self._optional_amount(
                text,
                rf"available RRSP contribution room for\s*{room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
            ),
        )

    @staticmethod
    def _text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    @staticmethod
    def _required(text: str, pattern: str, label: str) -> str:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if not match:
            raise ValueError(f"CRA notice {label} was not found")
        return match.group(1)

    def _line(self, text: str, number: str, description: str) -> Decimal:
        raw = self._required(
            text,
            rf"^{number}\s+{re.escape(description)}\s+([\d,]+(?:\.\d{{2}})?)",
            f"line {number}",
        )
        return self._amount(raw)

    @staticmethod
    def _taxpayer_name(text: str) -> str | None:
        match = re.search(r"(?m)^([A-Z][A-Z .'-]+)\n\d+\s+[A-Z]", text)
        return match.group(1).title() if match else None

    @staticmethod
    def _amount(raw: str) -> Decimal:
        return Decimal(raw.replace(",", "").replace(" ", ""))

    def _optional_amount(self, text: str, pattern: str) -> Decimal | None:
        matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        return self._amount(matches[-1]) if matches else None

    @staticmethod
    def _optional_int(text: str, pattern: str) -> int | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return int(match.group(1)) if match else None
