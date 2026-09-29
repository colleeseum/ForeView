from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from domain.parsed_tax_assessment import ParsedTaxAssessment


class RevenuQuebecNoticeParser:
    """Extract assessed Quebec tax totals from a Revenu Québec notice."""

    @staticmethod
    def detects(content: bytes) -> bool:
        try:
            text = RevenuQuebecNoticeParser._text(content)
        except (OSError, ValueError, PdfminerException):
            return False
        return "Notice of assessment" in text and "Revenu Québec" in text

    def parse(self, content: bytes) -> ParsedTaxAssessment:
        text = self._text(content)
        year = int(
            self._required(text, r"Notice of assessment\s+(\d{4}) taxation year", "tax year")
        )
        issued = (
            datetime.strptime(
                self._required(
                    text, r"Date of notice:\s+([A-Z][a-z]+ \d{1,2}, \d{4})", "issue date"
                ),
                "%B %d, %Y",
            )
            .date()
            .isoformat()
        )
        balance = self._amount(
            self._required(
                text,
                r"Balance due for this notice of assessment\s*=\s*\$?\s*([\d,]+\.\d{2})",
                "balance",
            )
        )
        return ParsedTaxAssessment(
            tax_year=year,
            jurisdiction="CA-QC",
            issued_on=issued,
            taxpayer_name=self._taxpayer_name(text),
            total_income=self._line(text, "199", "Total income"),
            net_income=self._line(text, "275", "Net income"),
            taxable_income=self._line(text, "299", "Taxable income"),
            net_tax=self._line(text, "432", "Income tax"),
            additional_contributions=self._line(text, "439", "QPIP premium", multiline=True),
            tax_withheld=self._line(text, "454", "Transferable portion", multiline=True),
            balance=balance,
        )

    @staticmethod
    def _text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    @staticmethod
    def _required(text: str, pattern: str, label: str) -> str:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if not match:
            raise ValueError(f"Revenu Québec notice {label} was not found")
        return match.group(1)

    def _line(
        self, text: str, number: str, description: str, *, multiline: bool = False
    ) -> Decimal:
        lines = text.splitlines()
        matching = next(
            (
                index
                for index, line in enumerate(lines)
                if re.match(rf"^{number}\s+{re.escape(description)}", line, re.IGNORECASE)
            ),
            None,
        )
        if matching is None:
            raise ValueError(f"Revenu Québec notice line {number} was not found")
        selected = lines[matching]
        if multiline and matching + 1 < len(lines):
            selected += " " + lines[matching + 1]
        values = re.findall(r"(?<!\d)([\d,]+\.\d{2})(?!\d)", selected)
        if not values:
            raise ValueError(f"Revenu Québec notice line {number} amount was not found")
        return self._amount(values[-1])

    @staticmethod
    def _taxpayer_name(text: str) -> str | None:
        match = re.search(
            r"First name and last name[^\n]*\n\s*([A-Za-zÀ-ÿ .'-]+?)\s+[A-Z][a-z]+ \d{1,2}, \d{4}",
            text,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _amount(raw: str) -> Decimal:
        return Decimal(raw.replace(",", "").replace(" ", ""))
