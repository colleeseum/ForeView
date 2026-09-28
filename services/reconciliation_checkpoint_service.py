"""Record reconciled ledger periods and detect later changes to them."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date, timedelta

from domain.money import MoneyInput, as_decimal
from domain.reconciliation_checkpoint import ReconciliationCheckpoint
from repositories.reconciliation_checkpoint_repository import (
    ReconciliationCheckpointRepository,
)
from repositories.transaction_repository import TransactionRepository


class ReconciliationCheckpointService:
    """Keep each account's reconciled periods and flag those an import has changed."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._checkpoints = ReconciliationCheckpointRepository(connection)
        self._transactions = TransactionRepository(connection)

    def record_statement(
        self, account_id: int, period_start: str, period_end: str, closing_balance: MoneyInput
    ) -> ReconciliationCheckpoint:
        """A statement period whose ledger activity matched the statement."""
        return self._record(account_id, period_start, period_end, closing_balance, "statement")

    def record_known_balance(
        self, account_id: int, reconciled_through: str, balance: MoneyInput
    ) -> ReconciliationCheckpoint:
        """A known balance that matched the ledger; covers everything since the last period."""
        previous = [
            checkpoint.reconciled_through
            for checkpoint in self._checkpoints.active_for_account(account_id)
            if checkpoint.reconciled_through < reconciled_through
        ]
        period_start = (
            (date.fromisoformat(max(previous)) + timedelta(days=1)).isoformat()
            if previous
            else None
        )
        return self._record(account_id, period_start, reconciled_through, balance, "manual")

    def withdraw_known_balance(self, account_id: int, reconciled_through: str) -> None:
        """Retire the manual reconciliation of a date that is being reconciled again."""
        for checkpoint in self._checkpoints.active_for_account(account_id):
            if (
                checkpoint.source == "manual"
                and checkpoint.reconciled_through == reconciled_through
            ):
                self._checkpoints.set_status(
                    checkpoint.id, ReconciliationCheckpoint.SUPERSEDED, checkpoint.difference
                )

    def locked_through(self, account_id: int) -> str | None:
        """The latest date covered by a reconciled period, if any."""
        checkpoints = self._checkpoints.active_for_account(account_id)
        return max((item.reconciled_through for item in checkpoints), default=None)

    def active(self, account_id: int) -> list[ReconciliationCheckpoint]:
        return self._checkpoints.active_for_account(account_id)

    def recheck(
        self, account_id: int, changed_dates: Iterable[str]
    ) -> list[ReconciliationCheckpoint]:
        """Flag reconciled periods whose ledger no longer matches what was reconciled.

        Returns the checkpoints now needing review.
        """
        dates = set(changed_dates)
        flagged = []
        for checkpoint in self._checkpoints.active_for_account(account_id):
            if not any(self._covers(checkpoint, day) for day in dates):
                continue
            net_change, count = self._transactions.period_totals(
                account_id, checkpoint.period_start, checkpoint.reconciled_through
            )
            if (net_change, count) == (checkpoint.net_change, checkpoint.transaction_count):
                continue
            difference = as_decimal(net_change) - as_decimal(checkpoint.net_change)
            self._checkpoints.set_status(
                checkpoint.id, ReconciliationCheckpoint.NEEDS_REVIEW, difference
            )
            refreshed = self._checkpoints.get(checkpoint.id)
            if refreshed is not None:
                flagged.append(refreshed)
        return flagged

    def _record(
        self,
        account_id: int,
        period_start: str | None,
        period_end: str,
        closing_balance: MoneyInput,
        source: str,
    ) -> ReconciliationCheckpoint:
        # A new reconciliation replaces earlier ones for any part of the same period.
        for checkpoint in self._checkpoints.active_for_account(account_id):
            overlaps = period_start is None or checkpoint.reconciled_through >= period_start
            if checkpoint.reconciled_through <= period_end and overlaps:
                self._checkpoints.set_status(
                    checkpoint.id, ReconciliationCheckpoint.SUPERSEDED, checkpoint.difference
                )
        net_change, count = self._transactions.period_totals(account_id, period_start, period_end)
        return self._checkpoints.create(
            account_id,
            period_start=period_start,
            reconciled_through=period_end,
            closing_balance=closing_balance,
            net_change=net_change,
            transaction_count=count,
            source=source,
        )

    @staticmethod
    def _covers(checkpoint: ReconciliationCheckpoint, day: str) -> bool:
        started = checkpoint.period_start is None or day >= checkpoint.period_start
        return started and day <= checkpoint.reconciled_through
