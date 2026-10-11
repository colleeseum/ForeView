# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Offline locale formatting at server presentation boundaries only."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from babel import Locale, UnknownLocaleError
from babel.dates import format_date
from babel.numbers import format_currency, format_decimal, format_percent

from domain.calendar_date import parse_calendar_date
from localization.service import LocalizationService


class ValueFormatter:
    def __init__(self, localization: LocalizationService, code: str) -> None:
        for candidate in localization.fallback_chain(code):
            try:
                self.locale = Locale.parse(candidate, sep="-")
                break
            except (ValueError, UnknownLocaleError):
                continue
        else:
            raise ValueError("No supported formatting locale")

    @staticmethod
    def _decimal(value: object) -> Decimal:
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise ValueError("Presentation amount must be finite")
        return amount

    def money(self, value: object) -> str:
        amount = self._decimal(value)
        with localcontext() as context:
            context.prec = max(28, len(amount.as_tuple().digits) + abs(amount.adjusted()) + 4)
            context.rounding = ROUND_HALF_UP
            return format_currency(amount, "CAD", locale=self.locale)

    def number(self, value: object, digits: int | None = None) -> str:
        pattern = None if digits is None else "#,##0" + ("." + "0" * digits if digits else "")
        amount = self._decimal(value)
        with localcontext() as context:
            context.prec = max(28, len(amount.as_tuple().digits) + abs(amount.adjusted()) + 4)
            context.rounding = ROUND_HALF_UP
            return format_decimal(
                amount,
                format=pattern,
                locale=self.locale,
                decimal_quantization=digits is not None,
            )

    def percent(self, value: object, digits: int = 2) -> str:
        pattern = self.locale.percent_formats[None].pattern.replace(
            "0", "0" + ("." + "0" * digits if digits else ""), 1
        )
        with localcontext() as context:
            context.rounding = ROUND_HALF_UP
            return format_percent(self._decimal(value), format=pattern, locale=self.locale)

    def date(self, value: object) -> str:
        if value is None or value == "":
            return ""
        parsed = parse_calendar_date(value)
        return format_date(parsed, format="medium", locale=self.locale) if parsed else str(value)
