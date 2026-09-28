from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Transaction:
    """One immutable financial transaction."""

    id: int
    account_id: int
    raw_transaction_id: int | None
    transaction_date: str
    amount: float
    description: str | None
    balance_after: float | None
    category: str | None
    transaction_type: str
