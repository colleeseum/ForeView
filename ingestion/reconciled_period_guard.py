"""Stop imports from silently changing reconciled periods."""

from __future__ import annotations

import sqlite3

from domain.reconciliation_checkpoint import ReconciliationCheckpoint
from ingestion.reconciled_period_change import ReconciledPeriodChange
from services.reconciliation_checkpoint_service import ReconciliationCheckpointService


class ReconciledPeriodGuard:
    """Track new transactions dated inside reconciled periods during one import.

    Call :meth:`admit` for each new transaction and :meth:`finish` after storing
    them, inside the import's database transaction. Without ``allow``, finish
    raises :class:`ReconciledPeriodChange` so the import rolls back and the user
    can be asked; with it, affected periods are rechecked and flagged if they
    no longer match what was reconciled.
    """

    def __init__(self, connection: sqlite3.Connection, *, allow: bool = False) -> None:
        self._checkpoints = ReconciliationCheckpointService(connection)
        self._allow = allow
        self._locked_through: dict[int, str | None] = {}
        self._entering: dict[int, list[str]] = {}

    def admit(self, account_id: int, transaction_date: str) -> None:
        if account_id not in self._locked_through:
            self._locked_through[account_id] = self._checkpoints.locked_through(account_id)
        locked_through = self._locked_through[account_id]
        if locked_through is not None and transaction_date <= locked_through:
            self._entering.setdefault(account_id, []).append(transaction_date)

    def finish(self) -> list[ReconciliationCheckpoint]:
        """Raise, or recheck affected periods; returns checkpoints now needing review."""
        entering, self._entering = self._entering, {}
        if entering and not self._allow:
            account_id, dates = next(iter(entering.items()))
            raise ReconciledPeriodChange(
                account_id, str(self._locked_through[account_id]), len(dates)
            )
        return [
            checkpoint
            for account_id, dates in entering.items()
            for checkpoint in self._checkpoints.recheck(account_id, dates)
        ]
