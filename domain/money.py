from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TypeAlias

MoneyInput: TypeAlias = Decimal | int | float | str
CENT = Decimal("0.01")
HUNDRED = Decimal(100)


def as_decimal(value: MoneyInput) -> Decimal:
    """Convert external numeric input without inheriting binary-float arithmetic."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value: MoneyInput) -> int:
    return int(as_decimal(value) * HUNDRED)


def from_cents(value: object) -> Decimal:
    if not isinstance(value, (int, str)):
        raise TypeError("Stored monetary cents must be an integer")
    return (Decimal(value) / HUNDRED).quantize(CENT)


def optional_cents(value: MoneyInput | None) -> int | None:
    return None if value is None else to_cents(value)


def optional_decimal_from_cents(value: object | None) -> Decimal | None:
    return None if value is None else from_cents(value)


def storage_decimal(value: MoneyInput) -> str:
    """Return normalized decimal text suitable for SQLite numeric affinity.

    The integer-cent column remains authoritative.  Writing normalized text to
    the compatibility REAL column avoids converting exact browser input through
    a binary float first.
    """
    return format(as_decimal(value), "f")


def optional_storage_decimal(value: MoneyInput | None) -> str | None:
    return None if value is None else storage_decimal(value)
