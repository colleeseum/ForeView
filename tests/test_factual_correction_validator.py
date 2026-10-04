# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from domain.income_tax_concept import (
    INCOME_TAX_CONCEPTS,
    income_tax_concept,
)
from services.factual_correction_validator import FactualCorrectionValidator


def test_income_tax_concepts_are_the_approved_shared_allowlist() -> None:
    assert tuple(concept.key for concept in INCOME_TAX_CONCEPTS) == (
        "employment_income",
        "oas_income",
        "cpp_qpp_benefits",
        "other_pension_income",
        "interest_investment_income",
        "total_income",
        "taxable_income",
        "rrsp_deduction",
        "net_federal_tax",
        "provincial_income_tax",
    )
    assert income_tax_concept("employment_income").label == "Employment income"


def test_validator_accepts_zero_and_normalizes_money_and_reason() -> None:
    values = FactualCorrectionValidator.validate(
        "1",
        "2025",
        "employment_income",
        "0",
        "  Supporting records show no income  ",
    )

    assert values.person_id == 1
    assert values.tax_year == 2025
    assert values.concept.key == "employment_income"
    assert values.amount == Decimal("0.00")
    assert values.reason == "Supporting records show no income"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("person_id", 0, "Person must be one or greater"),
        ("person_id", True, "Person must be an integer"),
        ("tax_year", 1899, "Tax year must be between 1900 and 2200"),
        ("tax_year", 2201, "Tax year must be between 1900 and 2200"),
        ("concept", "unknown", "Unsupported income and tax concept"),
        ("amount", "not-money", "Invalid amount"),
        ("amount", "NaN", "Invalid amount"),
        ("amount", "Infinity", "Invalid amount"),
        ("amount", "-0.01", "Corrected amount cannot be negative"),
        (
            "amount",
            "92233720368547758.08",
            "Corrected amount is outside the supported range",
        ),
        ("reason", "   ", "Correction reason is required"),
        ("reason", None, "Correction reason is required"),
    ],
)
def test_validator_rejects_invalid_correction_fields(field: str, value: Any, message: str) -> None:
    inputs: dict[str, Any] = {
        "person_id": 1,
        "tax_year": 2025,
        "concept": "employment_income",
        "amount": "100000",
        "reason": "Supporting records differ",
    }
    inputs[field] = value

    with pytest.raises(ValueError, match=message):
        FactualCorrectionValidator.validate(**inputs)


@pytest.mark.parametrize(
    ("value", "allow_zero", "message"),
    [
        (-1, True, "zero or greater"),
        (0, False, "one or greater"),
        (True, True, "must be an integer"),
        ("1.0", False, "must be an integer"),
    ],
)
def test_validator_rejects_invalid_expected_revisions(
    value: object, allow_zero: bool, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        FactualCorrectionValidator.expected_revision(value, allow_zero=allow_zero)
