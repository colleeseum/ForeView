# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.income_tax_concept import IncomeTaxConcept, income_tax_concept
from domain.money import MoneyInput, as_decimal, to_cents
from domain.validation_error import ValidationError

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
        validated_tax_year = FactualCorrectionValidator.integer(
            "Tax year", tax_year, code="correction_year_integer"
        )
        if not MIN_TAX_YEAR <= validated_tax_year <= MAX_TAX_YEAR:
            raise ValidationError(
                "correction_year_range",
                f"Tax year must be between {MIN_TAX_YEAR} and {MAX_TAX_YEAR}",
                minimum=MIN_TAX_YEAR,
                maximum=MAX_TAX_YEAR,
            )
        definition = FactualCorrectionValidator.concept(concept)
        try:
            validated_amount = as_decimal(amount)
        except ValueError as error:
            raise ValidationError(
                "correction_amount_invalid", str(error), amount=repr(amount)
            ) from error
        if validated_amount < 0:
            raise ValidationError(
                "correction_amount_negative", "Corrected amount cannot be negative"
            )
        if to_cents(validated_amount) > MAX_SQLITE_INTEGER:
            raise ValidationError(
                "correction_amount_range", "Corrected amount is outside the supported range"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("correction_reason_required", "Correction reason is required")
        return ValidatedFactualCorrection(
            person_id=validated_person_id,
            tax_year=validated_tax_year,
            concept=definition,
            amount=validated_amount,
            reason=reason.strip(),
        )

    @staticmethod
    def concept(value: object) -> IncomeTaxConcept:
        if not isinstance(value, str):
            raise ValidationError("correction_concept_required", "Concept is required")
        try:
            return income_tax_concept(value)
        except ValueError as error:
            raise ValidationError(
                "correction_concept_invalid", str(error), concept=value
            ) from error

    @staticmethod
    def expected_revision(value: object, *, allow_zero: bool) -> int:
        revision = FactualCorrectionValidator.integer(
            "Expected revision", value, code="correction_revision_integer"
        )
        minimum = 0 if allow_zero else 1
        if revision < minimum:
            qualifier = "zero or greater" if allow_zero else "one or greater"
            raise ValidationError(
                "correction_revision_nonnegative" if allow_zero else "correction_revision_positive",
                f"Expected revision must be {qualifier}",
            )
        return revision

    @staticmethod
    def positive_integer(name: str, value: object) -> int:
        number = FactualCorrectionValidator.integer(name, value)
        if number < 1:
            raise ValidationError("correction_person_positive", f"{name} must be one or greater")
        return number

    @staticmethod
    def integer(name: str, value: object, *, code: str = "correction_person_integer") -> int:
        if isinstance(value, bool):
            raise ValidationError(code, f"{name} must be an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as error:
                raise ValidationError(code, f"{name} must be an integer") from error
        raise ValidationError(code, f"{name} must be an integer")
