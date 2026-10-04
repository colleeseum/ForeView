from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AnnualTaxAssessment:
    """Government-assessed tax totals for one jurisdiction and tax year."""

    id: int
    person_id: int
    tax_year: int
    jurisdiction: str
    issued_on: str
    total_income: Decimal
    net_income: Decimal
    taxable_income: Decimal
    net_tax: Decimal
    additional_contributions: Decimal
    tax_withheld: Decimal
    balance: Decimal
    source: str
    source_version: str
    document_hash: str
