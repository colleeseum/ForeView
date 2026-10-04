# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.income_tax_concept import IncomeTaxConcept, income_tax_concept
from domain.money import MoneyInput, as_decimal, to_cents

MIN_TAX_YEAR = 1900
MAX_TAX_YEAR = 2200
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807


@dataclass(frozen=True, slots=True)
class ValidatedFactualCorrection:
    person_id: int
    tax_year: int
    concept: IncomeTaxConcept
    amount: Decimal
    reason: str


class FactualCorrectionValidator:
    """Validate factual correction input before persistence is attempted."""

    @staticmethod
    def validate(
        person_id: object,
        tax_year: object,
        concept: object,
        amount: MoneyInput,
        reason: object,
    ) -> ValidatedFactualCorrection:
        validated_person_id = FactualCorrectionValidator.positive_integer("Person", person_id)
        validated_tax_year = FactualCorrectionValidator.integer("Tax year", tax_year)
        if not MIN_TAX_YEAR <= validated_tax_year <= MAX_TAX_YEAR:
            raise ValueError(f"Tax year must be between {MIN_TAX_YEAR} and {MAX_TAX_YEAR}")
        if not isinstance(concept, str):
            raise ValueError("Concept is required")
        definition = income_tax_concept(concept)
        validated_amount = as_decimal(amount)
        if validated_amount < 0:
            raise ValueError("Corrected amount cannot be negative")
        if to_cents(validated_amount) > MAX_SQLITE_INTEGER:
            raise ValueError("Corrected amount is outside the supported range")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Correction reason is required")
        return ValidatedFactualCorrection(
            person_id=validated_person_id,
            tax_year=validated_tax_year,
            concept=definition,
            amount=validated_amount,
            reason=reason.strip(),
        )

    @staticmethod
    def expected_revision(value: object, *, allow_zero: bool) -> int:
        revision = FactualCorrectionValidator.integer("Expected revision", value)
        minimum = 0 if allow_zero else 1
        if revision < minimum:
            qualifier = "zero or greater" if allow_zero else "one or greater"
            raise ValueError(f"Expected revision must be {qualifier}")
        return revision

    @staticmethod
    def positive_integer(name: str, value: object) -> int:
        number = FactualCorrectionValidator.integer(name, value)
        if number < 1:
            raise ValueError(f"{name} must be one or greater")
        return number

    @staticmethod
    def integer(name: str, value: object) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as error:
                raise ValueError(f"{name} must be an integer") from error
        raise ValueError(f"{name} must be an integer")
