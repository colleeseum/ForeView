# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Read verified English and French Montréal annual municipal-tax accounts."""

from __future__ import annotations

import io
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain.parsed_expense_statement import ParsedExpenseStatement
from domain.validation_error import ValidationError
from ingestion.pdf_document import open_pdf

_DATE = r"([0-9]{2})[ \t]+([0-9]{2})[ \t]+([0-9]{4})"
_NUMBER = r"(?:[0-9]{1,3}(?: [0-9]{3})+|[0-9]+),[0-9]{2}"


@dataclass(frozen=True, slots=True)
class _AccountLayout:
    title: str
    header: str
    debtor: str
    separator: str
    details: str
    due: str
    total_label: str
    first: str
    second: str
    rate_unit: str
    payment_terms: str


_LAYOUTS = (
    _AccountLayout(
        "municipal tax account",
        "account number reference number access code taxation period billing date",
        "debtor(s) of the account",
        "to",
        "breakdown of account",
        "due date(s) day month year amount day month year amount account total",
        "account total",
        r"1\s*s\s*t:",
        r"2\s*n\s*d\s*:",
        r"/\$100",
        "terms of payment",
    ),
    _AccountLayout(
        "compte de taxes municipales",
        "numéro de compte numéro de référence code d'accès période d'imposition date de facturation",
        "débiteur(s) du compte",
        "au",
        "détail du compte",
        "total du compte\ndate(s) limite(s) jour mois année montant jour mois année montant",
        "total du compte",
        r"versement\(s\) 1\s*e\s*r\s*:",
        r"2\s*e\s*:",
        r"/100\$",
        "modalités de paiement",
    ),
)


@dataclass(frozen=True, slots=True)
class TaxAccountText:
    pages: tuple[str, ...]
    property_location: str = ""


def _read_pdf(content: bytes) -> TaxAccountText:
    try:
        with open_pdf(io.BytesIO(content)) as pdf:
            pages = tuple(page.extract_text() or "" for page in pdf.pages)
            location = ""
            if pdf.pages:
                front = pdf.pages[0]
                labels = front.search(r"Property location|Emplacement de la propriété", case=False)
                boroughs = front.search(r"Borough\s*:|Arrondissement\s*:", case=False)
                if len(labels) == len(boroughs) == 1:
                    label, borough = labels[0], boroughs[0]
                    if label["bottom"] < borough["top"]:
                        location = (
                            front.within_bbox(
                                # Printed header/value coordinates differ by tiny
                                # fractions of a point. Retain the entire first glyph.
                                (
                                    max(0, label["x0"] - 0.5),
                                    label["bottom"],
                                    front.width,
                                    borough["top"],
                                )
                            ).extract_text()
                            or ""
                        )
            return TaxAccountText(pages, location)
    except Exception as error:
        raise ValidationError(
            "expense_montreal_unreadable", "The Montréal municipal-tax PDF could not be read"
        ) from error


class MontrealTaxParser:
    VERSION = "2026.10.28"

    def __init__(self, text_reader: Callable[[bytes], TaxAccountText] = _read_pdf) -> None:
        self._text_reader = text_reader

    def _document(self, content: bytes) -> TaxAccountText:
        if not content:
            self._error("unreadable")
        document = self._text_reader(content)
        pages = document.pages
        if not pages or not any(page.strip() for page in pages):
            self._error("unreadable")
        return TaxAccountText(
            tuple(
                "\n".join(
                    " ".join(unicodedata.normalize("NFKC", line).split())
                    for line in page.splitlines()
                )
                for page in pages
            ),
            " ".join(document.property_location.split()),
        )

    @staticmethod
    def _layout(front: str) -> _AccountLayout | None:
        matches = [
            layout
            for layout in _LAYOUTS
            if (
                re.search(r"(?im)^" + re.escape(layout.title) + r" [0-9]{4}$", front) is not None
                and layout.header in front.casefold()
                and "ville de montréal" in front.casefold()
            )
        ]
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def _recognizes(cls, front: str) -> bool:
        return cls._layout(front) is not None

    def detects(self, content: bytes) -> bool:
        try:
            return self._recognizes(self._document(content).pages[0])
        except ValueError:
            return False

    @staticmethod
    def _error(kind: str) -> None:
        messages = {
            "unreadable": "The Montréal municipal-tax PDF could not be read",
            "format": "The PDF is not a supported Montréal annual municipal-tax account",
            "period": "Cannot verify the full calendar-year Montréal taxation period",
            "amount": "Cannot reconcile the Montréal annual account total, charges and installments",
            "identity": "Cannot verify the Montréal tax account and property location",
        }
        raise ValidationError(f"expense_montreal_{kind}", messages[kind])

    @classmethod
    def _money(cls, raw: str) -> Decimal:
        if not re.fullmatch(_NUMBER, raw):
            cls._error("amount")
        value = Decimal(raw.replace(" ", "").replace(",", "."))
        if value > Decimal("92233720368547758.07"):
            cls._error("amount")
        return value

    @staticmethod
    def _date(parts: tuple[str, ...]) -> date:
        day, month, year = map(int, parts)
        return date(year, month, day)

    def parse(self, content: bytes) -> ParsedExpenseStatement:
        document = self._document(content)
        pages = document.pages
        front = pages[0]
        layout = self._layout(front)
        if layout is None or len(pages) != 2:
            self._error("format")
        assert layout is not None
        # The reverse is explanatory only, including an optional interest-bearing plan.
        # Never use its payment amounts or the detachable coupons as extra expenses.
        if layout.payment_terms not in pages[1].casefold() or any(
            self._recognizes(page) for page in pages[1:]
        ):
            self._error("format")
        titles = re.findall(r"(?im)^" + re.escape(layout.title) + r" ([0-9]{4})$", front)
        if len(titles) != 1 or front.casefold().count(layout.header) != 1:
            self._error("format")
        year = int(titles[0])
        header = front.casefold().split(layout.header, 1)[1].split(layout.debtor, 1)[0]
        periods = re.findall(
            r"(?m)^" + _DATE + " " + layout.separator + " " + _DATE + r" " + _DATE + r"$", header
        )
        try:
            if len(periods) != 1:
                self._error("period")
            values = periods[0]
            start, end = self._date(values[:3]), self._date(values[3:6])
            self._date(values[6:])  # Validate the billing date, but never use it as the period.
            if start != date(year, 1, 1) or end != date(year, 12, 31):
                self._error("period")
        except ValueError as error:
            raise ValidationError(
                "expense_montreal_period",
                "Cannot verify the full calendar-year Montréal taxation period",
            ) from error

        accounts = re.findall(
            r"(?m)^([0-9]{6}-[0-9]{2}) [0-9]{8}-[0-9]{2}-[0-9]{2}-[0-9]{2}\b", header
        )
        if len(accounts) != 1 or not document.property_location:
            self._error("identity")

        lower = front.casefold()
        if lower.count(layout.due) != 1 or lower.count(layout.details) != 1:
            self._error("amount")
        summary = lower.split(layout.due, 1)[1].splitlines()
        summary = [line for line in summary if line.strip()]
        # Full-line matching excludes credits, malformed grouping, extra totals and signs.
        row = re.fullmatch(
            layout.first + " " + _DATE + r" (.+?) " + layout.second + " " + _DATE + r" (.+?)",
            summary[0] if summary else "",
        )
        if row is None:
            self._error("amount")
        assert row is not None
        groups = row.groups()
        first = self._money(groups[3])
        # The last two printed columns are the second installment and annual total.
        tail = re.fullmatch(r"(" + _NUMBER + r") (" + _NUMBER + r")", groups[7])
        if tail is None:
            self._error("amount")
        assert tail is not None
        second, total = (self._money(raw) for raw in tail.groups())
        try:
            first_due, second_due = self._date(groups[:3]), self._date(groups[4:7])
            if not start <= first_due < second_due <= end:
                self._error("period")
        except ValueError as error:
            raise ValidationError(
                "expense_montreal_period",
                "Cannot verify the full calendar-year Montréal taxation period",
            ) from error
        if first + second != total:
            self._error("amount")
        charge_section = lower.split(layout.details, 1)[1].split(layout.due, 1)[0]
        if layout.total_label in charge_section:
            self._error("amount")
        charges = charge_section.splitlines()[1:]
        amounts = []
        for line in charges:
            # Headings and watermark letters contain no numeric charge. Every numeric
            # row must have a rate followed by its reported, non-negative money column.
            if not re.search(r"[0-9]", line):
                continue
            match = re.fullmatch(r".+? " + layout.rate_unit + r" (.+)", line)
            if match is None:
                self._error("amount")
            assert match is not None
            amounts.append(self._money(match.group(1)))
        if not amounts or sum(amounts, Decimal(0)) != total:
            self._error("amount")
        return ParsedExpenseStatement(
            f"Montréal municipal property tax · {document.property_location} · {accounts[0]}",
            total,
            start,
            end,
            "annual_or_one_time",
        )
