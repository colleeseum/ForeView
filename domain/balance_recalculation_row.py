from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BalanceRecalculationRow:
    """Transaction facts needed to rebuild one running balance."""

    id: int
    transaction_date: str
    amount: float
    balance_after: float | None
    raw_data: str | None
