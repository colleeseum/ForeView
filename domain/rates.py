# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, DecimalException

from domain.validation_error import ValidationError

RATE_SCALE = Decimal("1000000")


def as_rate_decimal(value: Decimal | str | int | float) -> Decimal:
    """Parse an external rate using the authoritative millionth-rate precision."""
    try:
        rate = Decimal(str(value))
        if rate.is_finite():
            micros = to_rate_micros(rate)
            if -(2**63) <= micros < 2**63:
                return from_rate_micros(micros)
    except (DecimalException, ValueError, OverflowError):
        pass
    raise ValidationError("input_invalid_rate", f"Invalid rate: {value!r}", detail0=repr(value))


def to_rate_micros(value: Decimal | str | int | float) -> int:
    rate = Decimal(str(value))
    return int((rate * RATE_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_rate_micros(value: object) -> Decimal:
    if not isinstance(value, int):
        raise TypeError("Stored rate must be an integer")
    return Decimal(value) / RATE_SCALE
