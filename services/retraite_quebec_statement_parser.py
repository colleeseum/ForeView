from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from domain.parsed_public_pension_statement import ParsedPublicPensionStatement


class RetraiteQuebecStatementParser:
    """Extract official CPP/QPP earnings and estimates from a participation statement."""

    @staticmethod
    def detects(content: bytes) -> bool:
        try:
            text = RetraiteQuebecStatementParser._text(content)
        except (OSError, ValueError, PdfminerException):
            return False
        return "Statement of Participation" in text and "Québec Pension Plan" in text

    def parse(self, content: bytes) -> ParsedPublicPensionStatement:
        text = self._text(content)
        issued = (
            datetime.strptime(
                self._required(text, r"Date of issue:\s+(\d{1,2} [A-Z][a-z]+ \d{4})", "issue date"),
                "%d %B %Y",
            )
            .date()
            .isoformat()
        )
        earnings = tuple(
            (
                int(year),
                self._amount(qpp),
                self._amount(cpp),
                status or None,
            )
            for year, qpp, cpp, _total, status in re.findall(
                r"(?m)(?:^|\s)(\d{4})\*?\s+([\d ]+)\s*\$\s+([\d ]+)\s*\$\s+([\d ]+)\s*\$\s*([ABC]?)",
                text,
            )
        )
        if not earnings:
            raise ValueError("Retraite Québec pensionable earnings were not found")
        estimate_text = text.split(
            "Estimate of the amount of your retirement pension (monthly)", 1
        )[-1].split("Statement of Participation in the Québec Pension Plan", 1)[0]
        estimate_values = [self._amount(raw) for raw in re.findall(r"([\d ]+)\s*\$", estimate_text)]
        if len(estimate_values) < 4:
            raise ValueError("Retraite Québec retirement estimates were not found")
        continue_amounts = (estimate_values[1], estimate_values[0])
        stop_amounts = (estimate_values[3], estimate_values[2])
        return ParsedPublicPensionStatement(
            issued_on=issued,
            taxpayer_name=self._taxpayer_name(text),
            birth_date=self._birth_date(text),
            provider="QPP",
            excludes_second_enhancement=bool(
                re.search(r"only takes\s+into account the effect of the first component", text)
            ),
            earnings=earnings,
            estimates=(
                ("continue", 60, continue_amounts[0]),
                ("continue", 65, continue_amounts[1]),
                ("stop", 60, stop_amounts[0]),
                ("stop", 65, stop_amounts[1]),
            ),
        )

    @staticmethod
    def _text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    @staticmethod
    def _required(text: str, pattern: str, label: str) -> str:
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            raise ValueError(f"Retraite Québec statement {label} was not found")
        return match.group(1)

    @staticmethod
    def _taxpayer_name(text: str) -> str | None:
        match = re.search(r"(?m)^\s*(?:MR\.|MS\.|MRS\.)\s+([A-Z][A-Z .'-]+)$", text)
        return match.group(1).title() if match else None

    @staticmethod
    def _birth_date(text: str) -> str | None:
        match = re.search(r"Date of birth:\s+(\d{1,2} [A-Z][a-z]+ \d{4})", text)
        if not match:
            return None
        return datetime.strptime(match.group(1), "%d %B %Y").date().isoformat()

    @staticmethod
    def _amount(raw: str) -> Decimal:
        return Decimal(raw.replace(" ", ""))
