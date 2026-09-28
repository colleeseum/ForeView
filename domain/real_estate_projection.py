from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RealEstateProjection:
    """One immutable projected value for a real-estate asset."""

    id: int
    asset_id: int
    scenario_id: int | None
    projection_date: str
    projected_value: float
    projected_acb: float | None
    effective_tax_rate: float | None
    note: str | None
