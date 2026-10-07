# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Parse supported Hydro-Québec electricity bill PDFs."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from domain.money import as_decimal
from domain.parsed_expense_statement import ParsedExpenseStatement
from ingestion.pdf_document import open_pdf, pdf_page_texts

PdfTextReader = Callable[[bytes], list[str]]

_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
_MONTH_PATTERN = "|".join(_MONTHS)


def _read_pdf_text(content: bytes) -> list[str]:
    try:
        return pdf_page_texts(open_pdf, content)
    except Exception as error:
        raise ValueError("The Hydro-Québec PDF could not be read") from error


def _normalized(value: str) -> str:
    value = value.translate(str.maketrans({"−": "-", "–": "-", "—": "-"}))
    return unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode()


class HydroQuebecParser:
    """Extract current-bill expense evidence from Hydro-Québec PDFs."""

    VERSION = "2026.10.06"

    def __init__(self, text_reader: PdfTextReader = _read_pdf_text) -> None:
        self._text_reader = text_reader

    def detects(self, content: bytes) -> bool:
        try:
            text = self._text(content)
        except ValueError:
            return False
        return self._detects_text(text)

    def parse(self, content: bytes) -> ParsedExpenseStatement:
        text = self._text(content)
        if not self._detects_text(text):
            raise ValueError("The PDF is not a supported Hydro-Québec electricity bill")
        if self._is_epp_annual_review(text):
            raise ValueError(
                "Hydro-Québec Equalized Payments Plan annual-review bills are not supported"
            )
        period_start, period_end = self._extract_period(text)
        return ParsedExpenseStatement(
            suggested_identity="Hydro",
            amount=self._extract_current_bill_amount(text),
            period_start=period_start,
            period_end=period_end,
            period_kind="recurring_statement",
        )

    def _text(self, content: bytes) -> str:
        if not content:
            raise ValueError("The Hydro-Québec PDF is empty")
        pages = self._text_reader(content)
        text = "\n".join(page for page in pages if page.strip())
        if not text.strip():
            raise ValueError("The Hydro-Québec PDF contains no readable text")
        return _normalized(text)

    @staticmethod
    def _detects_text(text: str) -> bool:
        normalized = text.casefold()
        return (
            ("hydro-quebec" in normalized or "hydro quebec" in normalized)
            and re.search(r"facture d'?electricite", normalized) is not None
            and "detail des couts" in normalized
        )

    @staticmethod
    def _is_epp_annual_review(text: str) -> bool:
        normalized = text.casefold()
        french_heading = re.search(
            r"(?im)^\s*revision annuelle(?:\s*/\s*annual review)?\s*$", normalized
        )
        english_heading = re.search(r"(?im)^\s*annual review\s*$", normalized)
        french_review = french_heading is not None and any(
            marker in normalized
            for marker in ("mode de versements egaux", "solde mve", "mensualite")
        )
        english_review = english_heading is not None and any(
            marker in normalized
            for marker in ("equalized payments plan", "epp balance", "monthly installment")
        )
        return french_review or english_review

    @staticmethod
    def _extract_current_bill_amount(text: str) -> Decimal:
        amount_pattern = r"([0-9][0-9 .,]*[,.][0-9]{2})[ \t]*\$"
        match = re.search(
            rf"montant de la presente facture[ \t]+{amount_pattern}",
            text,
            flags=re.IGNORECASE,
        ) or re.search(
            rf"amount of this bill[ \t]+{amount_pattern}",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            raise ValueError("Cannot determine the amount of the current Hydro-Québec bill")
        raw = re.sub(r"\s+", "", match.group(1))
        if "," in raw and "." in raw:
            decimal_separator = "," if raw.rfind(",") > raw.rfind(".") else "."
            grouping_separator = "." if decimal_separator == "," else ","
            raw = raw.replace(grouping_separator, "").replace(decimal_separator, ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        try:
            amount = as_decimal(Decimal(raw))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("The Hydro-Québec bill amount is invalid") from error
        if amount < 0:
            raise ValueError("The Hydro-Québec bill amount cannot be negative")
        return amount

    @staticmethod
    def _extract_period(text: str) -> tuple[date, date]:
        matches = list(
            re.finditer(
                rf"detail des couts[^\n]*\n\s*du\s+"
                rf"(\d{{1,2}})\s+({_MONTH_PATTERN})\s+(\d{{4}})\s+au\s+"
                rf"(\d{{1,2}})\s+({_MONTH_PATTERN})\s+(\d{{4}})\s+"
                r"\((\d{1,3})\s+jours\)",
                text,
                flags=re.IGNORECASE,
            )
        )
        if not matches:
            raise ValueError("Cannot determine the Hydro-Québec electricity-use period")
        if len(matches) > 1:
            raise ValueError("Hydro-Québec bills with multiple service periods are not supported")
        match = matches[0]

        start = date(int(match.group(3)), _MONTHS[match.group(2).casefold()], int(match.group(1)))
        end = date(int(match.group(6)), _MONTHS[match.group(5).casefold()], int(match.group(4)))
        billed_days = int(match.group(7))
        if end <= start:
            raise ValueError("The Hydro-Québec electricity-use period is invalid")

        elapsed_days = (end - start).days
        if billed_days == elapsed_days:
            # Hydro's first date is the previous meter-reading boundary. The
            # billed calendar days begin on the following day.
            start += timedelta(days=1)
        elif billed_days != elapsed_days + 1:
            raise ValueError("The Hydro-Québec billed-day count does not match its dates")
        return start, end
