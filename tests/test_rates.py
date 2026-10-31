# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from decimal import Decimal

import pytest

from domain.rates import as_rate_decimal, from_rate_micros, to_rate_micros
from domain.validation_error import ValidationError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.025", "0.025"),
        (0.025123, "0.025123"),
        ("0.0251235", "0.025124"),
        ("-0.0251235", "-0.025124"),
        (0, "0"),
        (-1, "-1"),
    ],
)
def test_external_rate_preserves_millionths(value, expected):
    assert as_rate_decimal(value) == Decimal(expected)
    assert from_rate_micros(to_rate_micros(value)) == Decimal(expected)


@pytest.mark.parametrize(
    "value",
    ["bad", "", "NaN", "sNaN", "Infinity", "-Infinity", "1e999999", "1e16", "-1e16", True, None],
)
def test_invalid_rate_has_stable_validation_identity(value):
    with pytest.raises(ValidationError) as error:
        as_rate_decimal(value)
    assert error.value.code == "input_invalid_rate"


def test_stored_rate_requires_an_integer():
    with pytest.raises(TypeError):
        from_rate_micros("25000")
