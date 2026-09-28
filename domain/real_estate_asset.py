from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RealEstateAsset:
    """One immutable factual real-estate asset row."""

    id: int
    name: str
    property_type: str | None
    description: str | None
    estimated_value: float
    valuation_date: str
    acb: float | None
    ownership_share: float
    principal_residence: bool
    effective_tax_rate: float | None
    created_at: str
    updated_at: str
