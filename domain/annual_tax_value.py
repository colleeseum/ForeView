from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AnnualTaxValue:
    """A normalized factual value retained from a tax document."""

    id: int
    person_id: int
    tax_year: int
    effective_year: int
    document_kind: str
    jurisdiction: str
    concept: str
    description: str
    reported_amount: Decimal | None
    determined_amount: Decimal | None
    line_code: str | None
    source: str
    source_version: str
    document_hash: str
