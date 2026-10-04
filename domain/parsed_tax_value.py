from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ParsedTaxValue:
    """One useful value extracted from a filed return or assessment notice."""

    concept: str
    description: str
    reported_amount: Decimal | None
    determined_amount: Decimal | None = None
    line_code: str | None = None
    effective_year: int | None = None
