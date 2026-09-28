from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InvestmentHolding:
    """One immutable investment position at a valuation date."""

    id: int
    account_id: int
    valuation_date: str
    asset_class: str | None
    fund_code: str
    fund_name: str
    units: float
    unit_price: float
    market_value: float
    allocation_pct: float | None
    source_filename: str
