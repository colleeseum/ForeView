from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconciliationCheckpoint:
    """A period of an account's ledger confirmed against a statement or known balance.

    ``net_change`` and ``transaction_count`` describe the ledger for the period
    when it was reconciled, so a later change to the period can be detected.
    """

    id: int
    account_id: int
    period_start: str | None
    reconciled_through: str
    closing_balance: float
    net_change: float
    transaction_count: int
    source: str
    status: str
    difference: float | None
    created_at: str

    RECONCILED = "reconciled"
    NEEDS_REVIEW = "needs_review"
    SUPERSEDED = "superseded"
