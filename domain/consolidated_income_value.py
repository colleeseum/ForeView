from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ConsolidatedIncomeValue:
    """One resolved factual value in an annual income and tax snapshot."""

    concept: str
    label: str
    amount: Decimal
    source: str
    document_kind: str
    jurisdiction: str | None = None
    line_code: str | None = None
