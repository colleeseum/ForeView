from __future__ import annotations

import sqlite3

from domain.money import (
    MoneyInput,
    from_cents,
    optional_cents,
    optional_storage_decimal,
    storage_decimal,
    to_cents,
)
from domain.reconciliation_checkpoint import ReconciliationCheckpoint


class ReconciliationCheckpointRepository:
    """Persist reconciled ledger periods per account."""

    _SELECT = """SELECT id, account_id, period_start, reconciled_through, closing_balance_cents,
                        net_change_cents, transaction_count, source, status,
                        difference_cents, created_at
                 FROM reconciliation_checkpoints"""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        account_id: int,
        *,
        period_start: str | None,
        reconciled_through: str,
        closing_balance: MoneyInput,
        net_change: MoneyInput,
        transaction_count: int,
        source: str,
    ) -> ReconciliationCheckpoint:
        cursor = self._connection.execute(
            """INSERT INTO reconciliation_checkpoints(
                   account_id, period_start, reconciled_through, closing_balance,
                   closing_balance_cents, net_change, net_change_cents,
                   transaction_count, source, status
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                period_start,
                reconciled_through,
                storage_decimal(closing_balance),
                to_cents(closing_balance),
                storage_decimal(net_change),
                to_cents(net_change),
                transaction_count,
                source,
                ReconciliationCheckpoint.RECONCILED,
            ),
        )
        checkpoint = self.get(cursor.lastrowid)
        if checkpoint is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created reconciliation checkpoint could not be retrieved")
        return checkpoint

    def get(self, checkpoint_id: int | None) -> ReconciliationCheckpoint | None:
        if checkpoint_id is None:
            return None
        row = self._connection.execute(
            f"{self._SELECT} WHERE id = ?",  # noqa: S608
            (checkpoint_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def active_for_account(self, account_id: int) -> list[ReconciliationCheckpoint]:
        """Checkpoints not replaced by a later reconciliation, oldest period first."""
        rows = self._connection.execute(
            f"""{self._SELECT} WHERE account_id = ? AND status != ?
                ORDER BY reconciled_through, id""",  # noqa: S608
            (account_id, ReconciliationCheckpoint.SUPERSEDED),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def set_status(self, checkpoint_id: int, status: str, difference: MoneyInput | None) -> None:
        self._connection.execute(
            """UPDATE reconciliation_checkpoints
               SET status = ?, difference = ?, difference_cents = ? WHERE id = ?""",
            (
                status,
                optional_storage_decimal(difference),
                optional_cents(difference),
                checkpoint_id,
            ),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> ReconciliationCheckpoint:
        return ReconciliationCheckpoint(
            id=int(str(row[0])),
            account_id=int(str(row[1])),
            period_start=None if row[2] is None else str(row[2]),
            reconciled_through=str(row[3]),
            closing_balance=float(from_cents(row[4])),
            net_change=float(from_cents(row[5])),
            transaction_count=int(str(row[6])),
            source=str(row[7]),
            status=str(row[8]),
            difference=None if row[9] is None else float(from_cents(row[9])),
            created_at=str(row[10]),
        )
