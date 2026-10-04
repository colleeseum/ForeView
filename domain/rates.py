# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

RATE_SCALE = Decimal("1000000")


def to_rate_micros(value: Decimal | str | int | float) -> int:
    rate = Decimal(str(value))
    return int((rate * RATE_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_rate_micros(value: object) -> Decimal:
    if not isinstance(value, int):
        raise TypeError("Stored rate must be an integer")
    return Decimal(value) / RATE_SCALE
