from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatementReconciliation:
    """One immutable comparison between a statement and imported transactions."""

    id: int
    account_id: int
    import_batch_id: int
    statement_start: str
    statement_end: str
    opening_balance: float | None
    closing_balance: float | None
    statement_deposits: float | None
    statement_withdrawals: float | None
    csv_transaction_count: int
    csv_net_change: float | None
    difference: float | None
    status: str
    created_at: str
