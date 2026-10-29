# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Read the verified two-page bilingual Énergir gas-bill layout."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from domain.parsed_expense_statement import ParsedExpenseStatement
from domain.validation_error import ValidationError
from ingestion.pdf_document import open_pdf, pdf_page_texts

_MONTHS = dict(zip("ja fe mr al ma jn jl au se oc no de".split(), range(1, 13), strict=True))
_DATE = r"([0-9]{4})[ \t]+(" + "|".join(_MONTHS) + r")[ \t]+([0-9]{1,2})"
_RANGE = _DATE + r"[ \t]+au[ \t]*/[ \t]*to[ \t]+" + _DATE
_MONEY = re.compile(r"(?<!\S)([+\-]?[ \t]*[0-9][0-9 .,\t]*)[ \t]*\$([ \t]*cr)?")
_NUMBER = re.compile(r"[+\-]?(?:[0-9]{1,3}(?: [0-9]{3})+|[0-9]+)[,.][0-9]{2}")


def _read_pdf(content: bytes) -> list[str]:
    try:
        return pdf_page_texts(open_pdf, content)
    except Exception as error:
        raise ValidationError(
            "expense_energir_unreadable", "The Énergir PDF could not be read"
        ) from error


class EnergirParser:
    VERSION = "2026.10.28"

    def __init__(self, text_reader: Callable[[bytes], list[str]] = _read_pdf) -> None:
        self._text_reader = text_reader

    def _pages(self, content: bytes) -> list[str]:
        if not content:
            raise ValidationError("expense_energir_unreadable", "The Énergir PDF could not be read")
        pages = self._text_reader(content)
        if not any(page.strip() for page in pages):
            raise ValidationError("expense_energir_unreadable", "The Énergir PDF could not be read")
        return [
            "".join(
                "-" if unicodedata.category(char) == "Pd" or char == "−" else char
                for char in unicodedata.normalize("NFKD", page)
                if not unicodedata.combining(char)
            ).casefold()
            for page in pages
        ]

    @staticmethod
    def _recognizes(text: str) -> bool:
        return all(
            marker in text
            for marker in (
                "energir",
                "montant facture pour la periode du",
                "volume facture / volume billed:",
            )
        )

    def detects(self, content: bytes) -> bool:
        try:
            return self._recognizes(self._pages(content)[0])
        except ValueError:
            return False

    def parse(self, content: bytes) -> ParsedExpenseStatement:
        pages = self._pages(content)
        text = "\n".join(pages)
        if not self._recognizes(pages[0]):
            raise ValidationError(
                "expense_energir_format", "The PDF is not a supported bilingual Énergir gas bill"
            )
        heading = "montant facture pour la periode du"
        block = pages[0].partition(heading)[2].split("\nmontant courant", 1)[0]
        if (
            len(pages) != 2
            or text.count(heading) != 1
            or any(
                marker in text
                for marker in (
                    "mode de paiements egaux",
                    "equal payments",
                    "mensualite",
                    "solde mpe",
                    "revision annuelle",
                    "annual review",
                    "facture corrigee",
                    "facture rectificative",
                    "corrected bill",
                )
            )
            or re.search(r"\b(?:mpe|epp)\b", text) is not None
            or re.search(r"\b(?:location|rental)\b", block) is not None
        ):
            raise ValidationError(
                "expense_energir_unsupported",
                "Énergir bundled, equal-payment, corrected or multi-bill documents require manual entry",
            )
        if re.search(r"\$\s*\(?\s*(?:cr|credit)\b", block):
            self._amount_error()
        start, end = self._period(pages, block)
        pretax = self._component(block, r"volume facture / volume billed:")
        gst = self._component(block, r"\btps[ \t]*/[ \t]*gst\b")
        qst = self._component(block, r"\btvq[ \t]*/[ \t]*pst\b")
        totals = list(re.finditer(r"\btotal[ \t]+([^\n]+)", block))
        # History's annual totals do not match: their labels contain words, not money.
        totals = [match for match in totals if re.match(r"[+\-]?[0-9]", match.group(1))]
        if len(totals) != 1:
            self._amount_error()
        tail = totals[0].group(1)
        columns = self._amounts(tail)
        if not 1 <= len(columns) <= 2 or _MONEY.sub("", tail).strip() or len(set(columns)) != 1:
            self._amount_error()
        amount = columns[0]
        if amount != pretax + gst + qst:
            self._amount_error()
        return ParsedExpenseStatement("Énergir", amount, start, end, "recurring_statement")

    @staticmethod
    def _amount_error() -> None:
        raise ValidationError(
            "expense_energir_amount",
            "Cannot verify the current-period Énergir charge including taxes",
        )

    @classmethod
    def _amounts(cls, line: str) -> list[Decimal]:
        values = []
        for match in _MONEY.finditer(line):
            raw = match.group(1).strip()
            if (
                match.group(2)
                or not _NUMBER.fullmatch(raw)
                or line[: match.start()].rstrip().endswith(("-", "("))
            ):
                cls._amount_error()
            amount = Decimal(raw.replace(" ", "").replace(",", "."))
            # Authoritative SQLite money is signed 64-bit integer cents.
            if amount < 0 or amount > Decimal("92233720368547758.07"):
                cls._amount_error()
            values.append(amount)
        return values

    @classmethod
    def _component(cls, block: str, label: str) -> Decimal:
        lines = re.findall(label + r"[^\n]*", block)
        if len(lines) != 1:
            cls._amount_error()
        amounts = cls._amounts(lines[0])
        if len(amounts) != 1:
            cls._amount_error()
        return amounts[0]

    @staticmethod
    def _dates(match: re.Match[str]) -> tuple[date, date]:
        values = match.groups()
        return (
            date(int(values[0]), _MONTHS[values[1]], int(values[2])),
            date(int(values[3]), _MONTHS[values[4]], int(values[5])),
        )

    @classmethod
    def _period(cls, pages: list[str], block: str) -> tuple[date, date]:
        header = list(re.finditer(r"(?m)^pour la periode du[ \t]+" + _RANGE, pages[0]))
        charge = list(re.finditer(_RANGE, block))
        detail = list(
            re.finditer(
                r"periode / period[ \t]*:[ \t]*" + _RANGE + r"[ \t]+([0-9]{1,3})[ \t]+jours / days",
                pages[1],
            )
        )
        try:
            if len(header) != 1 or len(charge) != 1 or len(detail) != 1:
                raise ValueError("Missing or ambiguous periods")
            start, end = cls._dates(header[0])
            if (start, end) != cls._dates(charge[0]) or (start, end) != cls._dates(detail[0]):
                raise ValueError("Inconsistent periods")
            if end < start or (end - start).days + 1 != int(detail[0].group(7)):
                raise ValueError("Inconsistent inclusive day count")
        except ValueError as error:
            raise ValidationError(
                "expense_energir_period",
                "Cannot verify the Énergir service dates and billed day count",
            ) from error
        return start, end
