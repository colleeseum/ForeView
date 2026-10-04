# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.balance_snapshot import BalanceSnapshot
from domain.money import (
    MoneyInput,
    as_decimal,
    from_cents,
    optional_cents,
    optional_storage_decimal,
    storage_decimal,
    to_cents,
)


class BalanceSnapshotRepository:
    """Persist and retrieve factual account-balance observations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(
        self,
        account_id: int,
        snapshot_date: str,
        amount: MoneyInput,
        interest_rate: float | None = None,
        *,
        contribution: MoneyInput | None = None,
        lock_date: str | None = None,
        maturity_date: str | None = None,
        source_sheet: str = "application",
        source_address: str = "manual",
    ) -> None:
        normalized_amount = as_decimal(amount)
        if normalized_amount < 0:
            raise ValueError("Balance cannot be negative")
        if interest_rate is not None and interest_rate < 0:
            raise ValueError("Interest rate cannot be negative")
        self._connection.execute(
            """
            INSERT OR REPLACE INTO balance_snapshots(
                account_id, snapshot_date, amount, contribution, lock_date,
                amount_cents, contribution_cents, maturity_date, interest_rate,
                source_sheet, source_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                snapshot_date,
                storage_decimal(normalized_amount),
                optional_storage_decimal(contribution),
                lock_date,
                to_cents(normalized_amount),
                optional_cents(contribution),
                maturity_date,
                interest_rate,
                source_sheet,
                source_address,
            ),
        )

    def record_reported(
        self,
        account_id: int,
        snapshot_date: str,
        amount: MoneyInput,
        *,
        source_sheet: str,
        source_address: str,
    ) -> None:
        """Store a balance reported by an institution, which may be negative (e.g. margin)."""
        self._connection.execute(
            """INSERT OR REPLACE INTO balance_snapshots(
                   account_id, snapshot_date, amount, amount_cents, source_sheet, source_address
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                snapshot_date,
                storage_decimal(amount),
                to_cents(amount),
                source_sheet,
                source_address,
            ),
        )

    def remove_manual_reconciliation(self, account_id: int, snapshot_date: str) -> bool:
        """Delete the balance a manual reconciliation recorded for a date, if any."""
        cursor = self._connection.execute(
            """DELETE FROM balance_snapshots
               WHERE account_id = ? AND snapshot_date = ?
                 AND source_sheet = 'Manual reconciliation' AND source_address = 'transactions'""",
            (account_id, snapshot_date),
        )
        return cursor.rowcount > 0

    def normalize_percentage_rates(self) -> None:
        """Convert legacy rates stored as percentages (e.g. 4.5) into fractions (0.045)."""
        self._connection.execute(
            "UPDATE balance_snapshots SET interest_rate = interest_rate / 100 WHERE interest_rate > 1"
        )

    def annual_totals(self) -> list[dict[str, object]]:
        """Total balance per snapshot date and source."""
        rows = self._connection.execute(
            """
            SELECT snapshot_date, source_sheet, SUM(amount_cents) / 100.0 AS total_amount,
                   COUNT(*) AS account_count
            FROM balance_snapshots GROUP BY snapshot_date, source_sheet ORDER BY snapshot_date
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get(self, snapshot_id: int | None) -> BalanceSnapshot | None:
        if snapshot_id is None:
            return None
        row = self._connection.execute(
            """SELECT id, account_id, snapshot_date, amount_cents, contribution_cents, lock_date,
                      maturity_date, interest_rate, source_sheet, source_address
               FROM balance_snapshots WHERE id = ?""",
            (snapshot_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_account(self, account_id: int) -> list[BalanceSnapshot]:
        rows = self._connection.execute(
            """SELECT id, account_id, snapshot_date, amount_cents, contribution_cents, lock_date,
                      maturity_date, interest_rate, source_sheet, source_address
               FROM balance_snapshots WHERE account_id = ? ORDER BY snapshot_date, id""",
            (account_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> BalanceSnapshot:
        snapshot_id = row[0]
        account_id = row[1]
        if not isinstance(snapshot_id, int) or not isinstance(account_id, int):
            raise TypeError("Balance snapshot identifiers must be integers")
        return BalanceSnapshot(
            id=snapshot_id,
            account_id=account_id,
            snapshot_date=str(row[2]),
            amount=float(from_cents(row[3])),
            contribution=None if row[4] is None else float(from_cents(row[4])),
            lock_date=str(row[5]) if row[5] is not None else None,
            maturity_date=str(row[6]) if row[6] is not None else None,
            interest_rate=BalanceSnapshotRepository._optional_float(row[7]),
            source_sheet=str(row[8]),
            source_address=str(row[9]),
        )

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("Balance snapshot numeric value has an invalid type")
        return float(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        if not isinstance(value, (int, float, str)):
            raise TypeError("Balance snapshot numeric value has an invalid type")
        return float(value)
