# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Exact decimal field types used by public-rule models."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field


def _exact_decimal(value: object) -> Decimal:
    if isinstance(value, float):
        raise ValueError(
            "Decimal values must be provided as strings, integers, or Decimal instances"
        )
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid decimals")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as error:
        raise ValueError("Invalid decimal value") from error
    if not result.is_finite():
        raise ValueError("Decimal values must be finite")
    return result


ExactDecimal = Annotated[Decimal, BeforeValidator(_exact_decimal)]
NonNegativeDecimal = Annotated[ExactDecimal, Field(ge=Decimal("0"))]
RateDecimal = Annotated[ExactDecimal, Field(ge=Decimal("0"), le=Decimal("1"))]
