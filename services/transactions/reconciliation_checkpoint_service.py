# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

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
        return self._record(
            account_id,
            self._canonical_date(period_start),
            self._canonical_date(period_end),
            closing_balance,
            "statement",
        )

    def record_known_balance(
        self, account_id: int, reconciled_through: str, balance: MoneyInput
    ) -> ReconciliationCheckpoint:
        """A known balance that matched the ledger; covers everything since the last period."""
        reconciled_through = self._canonical_date(reconciled_through)
        previous = []
        for checkpoint in self._checkpoints.active_for_account(account_id):
            try:
                stored_date = self._canonical_date(checkpoint.reconciled_through)
            except ValueError:
                continue
            if stored_date < reconciled_through:
                previous.append(stored_date)
        period_start = (
            (date.fromisoformat(max(previous)) + timedelta(days=1)).isoformat()
            if previous
            else None
        )
        return self._record(account_id, period_start, reconciled_through, balance, "manual")

    def withdraw_known_balance(self, account_id: int, reconciled_through: str) -> None:
        """Retire the manual reconciliation of a date that is being reconciled again."""
        reconciled_through = self._canonical_date(reconciled_through)
        for checkpoint in self._checkpoints.active_for_account(account_id):
            try:
                stored_date = self._canonical_date(checkpoint.reconciled_through)
            except ValueError:
                continue
            if checkpoint.source == "manual" and stored_date == reconciled_through:
                self._checkpoints.set_status(
                    checkpoint.id, ReconciliationCheckpoint.SUPERSEDED, checkpoint.difference
                )

    def locked_through(self, account_id: int) -> str | None:
        """The latest date covered by a reconciled period, if any."""
        checkpoints = self._checkpoints.active_for_account(account_id)
        dates = []
        for checkpoint in checkpoints:
            try:
                dates.append(self._canonical_date(checkpoint.reconciled_through))
            except ValueError:
                continue
        return max(dates, default=None)

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
            try:
                checkpoint_end = self._canonical_date(checkpoint.reconciled_through)
            except ValueError:
                continue
            overlaps = period_start is None or checkpoint_end >= period_start
            if checkpoint_end <= period_end and overlaps:
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
        try:
            normalized_day = ReconciliationCheckpointService._canonical_date(day)
            period_start = (
                None
                if checkpoint.period_start is None
                else ReconciliationCheckpointService._canonical_date(checkpoint.period_start)
            )
            period_end = ReconciliationCheckpointService._canonical_date(
                checkpoint.reconciled_through
            )
        except ValueError:
            return False
        started = period_start is None or normalized_day >= period_start
        return started and normalized_day <= period_end

    @staticmethod
    def _canonical_date(value: str) -> str:
        return date.fromisoformat(value).isoformat()
