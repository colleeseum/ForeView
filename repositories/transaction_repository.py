# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from collections.abc import Collection, Mapping
from datetime import date
from typing import cast

from domain.balance_anchor import BalanceAnchor
from domain.balance_recalculation_row import BalanceRecalculationRow
from domain.calendar_date import (
    balance_event_sort_key,
    calendar_date_sort_key,
    canonical_date_or_stored,
    parse_calendar_date,
)
from domain.money import from_cents, optional_cents, to_cents
from domain.transaction import Transaction


class TransactionRepository:
    """Persist transactions and provide the factual rows needed by transaction services."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get(self, transaction_id: int | None) -> Transaction | None:
        if transaction_id is None:
            return None
        row = self._connection.execute(
            f"{self._SELECT} WHERE id = ?",  # noqa: S608 - static query fragment
            (transaction_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def create(
        self,
        account_id: int,
        transaction_date: str,
        amount: float,
        *,
        raw_transaction_id: int | None = None,
        description: str | None = None,
        balance_after: float | None = None,
        category: str | None = None,
        transaction_type: str = "unclassified",
    ) -> Transaction:
        cursor = self._connection.execute(
            """INSERT INTO transactions(
                   account_id, raw_transaction_id, transaction_date, amount,
                   amount_cents, description, balance_after, balance_after_cents,
                   category, transaction_type
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                raw_transaction_id,
                transaction_date,
                amount,
                to_cents(amount),
                description,
                balance_after,
                optional_cents(balance_after),
                category,
                transaction_type,
            ),
        )
        transaction = self.get(cursor.lastrowid)
        if transaction is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created transaction could not be retrieved")
        return transaction

    def create_if_absent(
        self,
        account_id: int,
        transaction_date: str,
        amount: float,
        *,
        raw_transaction_id: int | None = None,
        description: str | None = None,
        balance_after: float | None = None,
        category: str | None = None,
        transaction_type: str = "unclassified",
    ) -> Transaction | None:
        cursor = self._connection.execute(
            """INSERT OR IGNORE INTO transactions(
                   account_id, raw_transaction_id, transaction_date, amount,
                   amount_cents, description, balance_after, balance_after_cents,
                   category, transaction_type
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                raw_transaction_id,
                transaction_date,
                amount,
                to_cents(amount),
                description,
                balance_after,
                optional_cents(balance_after),
                category,
                transaction_type,
            ),
        )
        return self.get(cursor.lastrowid) if cursor.rowcount else None

    def list_for_account(self, account_id: int) -> list[Transaction]:
        rows = self._connection.execute(
            f"{self._SELECT} WHERE account_id = ? ORDER BY transaction_date, id",  # noqa: S608
            (account_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    # Columns a caller may match stored transactions on; see count_matching.
    MATCHABLE_COLUMNS = frozenset(
        {"transaction_date", "amount", "description", "transaction_type", "balance_after"}
    )

    def count_matching(self, account_id: int, values: Mapping[str, object]) -> int:
        """How many of an account's transactions have exactly these column values."""
        unknown = set(values) - self.MATCHABLE_COLUMNS
        if unknown or not values:
            raise ValueError(f"Cannot match transactions on {sorted(unknown) or 'no columns'}")
        stored_values = {
            (f"{column}_cents" if column in {"amount", "balance_after"} else column): (
                None
                if value is None
                else to_cents(cast(str | int | float, value))
                if column in {"amount", "balance_after"}
                else value
            )
            for column, value in values.items()
        }
        columns = sorted(stored_values)
        # Column names come from the fixed set above; IS compares NULLs as equal.
        conditions = " AND ".join(f"{column} IS ?" for column in columns)
        row = self._connection.execute(
            f"SELECT COUNT(*) FROM transactions WHERE account_id = ? AND {conditions}",  # noqa: S608  # nosec
            (account_id, *(stored_values[column] for column in columns)),
        ).fetchone()
        return int(row[0])

    def period_totals(
        self, account_id: int, period_start: str | None, period_end: str
    ) -> tuple[float, int]:
        """Net change and number of an account's transactions dated in a period.

        ``period_start`` is inclusive; None means from the first transaction.
        """
        start = date.fromisoformat(period_start) if period_start is not None else None
        end = date.fromisoformat(period_end)
        rows = self._connection.execute(
            "SELECT transaction_date, amount_cents FROM transactions WHERE account_id = ?",
            (account_id,),
        ).fetchall()
        included = [
            int(row[1])
            for row in rows
            if (transaction_date := parse_calendar_date(row[0])) is not None
            and (start is None or transaction_date >= start)
            and transaction_date <= end
        ]
        return float(from_cents(sum(included))), len(included)

    def amounts_between(self, account_id: int, start_date: str, end_date: str) -> list[float]:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        rows = self._connection.execute(
            "SELECT id, transaction_date, amount_cents FROM transactions WHERE account_id = ?",
            (account_id,),
        ).fetchall()
        included = [
            (transaction_date, int(row[0]), int(row[2]))
            for row in rows
            if (transaction_date := parse_calendar_date(row[1])) is not None
            and start <= transaction_date <= end
        ]
        included.sort(key=lambda item: item[:2])
        return [float(from_cents(item[2])) for item in included]

    def id_for_raw_transaction(self, raw_transaction_id: int) -> int | None:
        row = self._connection.execute(
            "SELECT id FROM transactions WHERE raw_transaction_id = ? ORDER BY id LIMIT 1",
            (raw_transaction_id,),
        ).fetchone()
        return int(row[0]) if row else None

    def update_details(
        self,
        transaction_id: int,
        *,
        transaction_date: str,
        amount: float,
        description: str | None,
        category: str | None,
        transaction_type: str,
    ) -> None:
        self._connection.execute(
            """UPDATE transactions SET transaction_date = ?, amount = ?, amount_cents = ?,
               description = ?, category = ?, transaction_type = ? WHERE id = ?""",
            (
                transaction_date,
                amount,
                to_cents(amount),
                description,
                category,
                transaction_type,
                transaction_id,
            ),
        )

    def clear_balances_from_source(self, account_id: int, source: str) -> None:
        """Drop stored balances on an account's rows imported from one raw source."""
        self._connection.execute(
            """UPDATE transactions SET balance_after = NULL, balance_after_cents = NULL
               WHERE account_id = ? AND raw_transaction_id IN (
                   SELECT r.id FROM raw_transactions r
                   WHERE r.id = transactions.raw_transaction_id
                     AND json_extract(r.raw_data, '$.source') = ?
               )""",
            (account_id, source),
        )

    def descriptions_from_source(
        self, source: str, *, blank_only: bool = False
    ) -> list[tuple[int, str | None, str]]:
        """(id, description, raw data) for every transaction imported from one raw source."""
        rows = self._connection.execute(
            """SELECT t.id, t.description, r.raw_data
               FROM transactions t
               JOIN raw_transactions r ON r.id = t.raw_transaction_id
               WHERE json_extract(r.raw_data, '$.source') = ?
                 AND (? = 0 OR t.description = '')""",
            (source, int(blank_only)),
        ).fetchall()
        return [(int(row[0]), row[1], str(row[2])) for row in rows]

    def update_description(self, transaction_id: int, description: str) -> None:
        self._connection.execute(
            "UPDATE transactions SET description = ? WHERE id = ?", (description, transaction_id)
        )

    def classify(
        self,
        transaction_id: int,
        *,
        description: str | None,
        category: str,
        transaction_type: str,
    ) -> None:
        self._connection.execute(
            """UPDATE transactions SET description = ?, category = ?, transaction_type = ?
               WHERE id = ?""",
            (description, category, transaction_type, transaction_id),
        )

    def account_exists(self, account_id: int) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            is not None
        )

    def account_asset_kind(self, account_id: int) -> str | None:
        row = self._connection.execute(
            "SELECT asset_kind FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return str(row[0]) if row else None

    def latest_snapshot(self, account_id: int) -> BalanceAnchor | None:
        rows = self._connection.execute(
            """SELECT id, snapshot_date, amount_cents
               FROM balance_snapshots WHERE account_id = ?""",
            (account_id,),
        ).fetchall()
        candidates = [
            (snapshot_date, int(row[0]), int(row[2]))
            for row in rows
            if (snapshot_date := parse_calendar_date(row[1])) is not None
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item[:2])
        return BalanceAnchor(latest[0].isoformat(), float(from_cents(latest[2])))

    def latest_known_balance(self, account_id: int, balance_date: str) -> tuple[str, float] | None:
        """The latest transaction or snapshot balance on or before a date."""
        target = date.fromisoformat(balance_date)
        candidates: list[tuple[date, int, int, int]] = []
        sources = (
            (
                1,
                self._connection.execute(
                    """SELECT id, transaction_date, balance_after_cents FROM transactions
                       WHERE account_id = ? AND balance_after_cents IS NOT NULL""",
                    (account_id,),
                ).fetchall(),
            ),
            (
                0,
                self._connection.execute(
                    """SELECT id, snapshot_date, amount_cents FROM balance_snapshots
                       WHERE account_id = ?""",
                    (account_id,),
                ).fetchall(),
            ),
        )
        for source_priority, rows in sources:
            for row in rows:
                candidate_date = parse_calendar_date(row[1])
                if candidate_date is None:
                    continue
                if candidate_date <= target:
                    candidates.append((candidate_date, source_priority, int(row[0]), int(row[2])))
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item[:3])
        return latest[0].isoformat(), float(from_cents(latest[3]))

    def has_snapshot_source(self, account_id: int, sources: Collection[str]) -> bool:
        """Whether an account has a snapshot from any caller-defined source."""
        source_names = tuple(sources)
        if not source_names:
            return False
        placeholders = ", ".join("?" for _ in source_names)
        row = self._connection.execute(
            f"""SELECT 1 FROM balance_snapshots
                WHERE account_id = ? AND source_sheet IN ({placeholders}) LIMIT 1""",  # noqa: S608  # nosec
            (account_id, *source_names),
        ).fetchone()
        return row is not None

    def rows_for_balance_recalculation(
        self,
        account_id: int,
        excluded_sources: Collection[str] = (),
        *,
        include_excluded: bool = False,
        include_malformed: bool = False,
    ) -> list[BalanceRecalculationRow]:
        source_names = tuple(excluded_sources)
        source_filter = ""
        parameters: list[object] = [account_id]
        if source_names and not include_excluded:
            placeholders = ", ".join("?" for _ in source_names)
            source_filter = (
                f"AND COALESCE(json_extract(r.raw_data, '$.source'), '') NOT IN ({placeholders})"
            )
            parameters.extend(source_names)
        rows = self._connection.execute(
            f"""SELECT t.id, t.transaction_date, t.amount_cents, t.balance_after_cents, r.raw_data
               FROM transactions t
               LEFT JOIN raw_transactions r ON r.id = t.raw_transaction_id
               WHERE t.account_id = ?
                 {source_filter}""",  # noqa: S608  # nosec
            parameters,
        ).fetchall()
        candidates = [
            (
                calendar_date_sort_key(row[1], int(row[0])),
                int(row[0]),
                BalanceRecalculationRow(
                    id=int(row[0]),
                    transaction_date=canonical_date_or_stored(row[1]),
                    amount=float(from_cents(row[2])),
                    balance_after=None if row[3] is None else float(from_cents(row[3])),
                    raw_data=row[4],
                ),
            )
            for row in rows
            if include_malformed or parse_calendar_date(row[1]) is not None
        ]
        candidates.sort(key=lambda item: item[:2], reverse=True)
        return [item[2] for item in candidates]

    def set_balance(self, transaction_id: int, balance_after: float) -> None:
        self._connection.execute(
            "UPDATE transactions SET balance_after = ?, balance_after_cents = ? WHERE id = ?",
            (balance_after, to_cents(balance_after), transaction_id),
        )

    def clear_balance(self, transaction_id: int) -> None:
        self._connection.execute(
            "UPDATE transactions SET balance_after = NULL, balance_after_cents = NULL WHERE id = ?",
            (transaction_id,),
        )

    def non_iso_dates(self) -> list[tuple[int, str]]:
        rows = self._connection.execute(
            """SELECT id, transaction_date FROM transactions
               WHERE transaction_date NOT GLOB '????-??-??'"""
        ).fetchall()
        return [(int(row[0]), str(row[1])) for row in rows]

    def update_date(self, transaction_id: int, transaction_date: str) -> None:
        self._connection.execute(
            "UPDATE transactions SET transaction_date = ? WHERE id = ?",
            (transaction_date, transaction_id),
        )

    def summary_rows(
        self, account_id: int | None, account_type: str | None
    ) -> list[dict[str, object]]:
        filters = ""
        params: list[object] = []
        if account_id is not None:
            if self.account_asset_kind(account_id) == "account":
                filters = "WHERE (t.account_id = ? OR a.parent_account_id = ?)"
                params.extend([account_id, account_id])
            else:
                filters = "WHERE t.account_id = ?"
                params.append(account_id)
        if account_type is not None:
            filters += " AND" if filters else "WHERE"
            filters += " a.account_type = ?"
            params.append(account_type)
        query = self._SUMMARY_SELECT.replace("__TRANSACTION_FILTER__", filters)
        result = [dict(row) for row in self._connection.execute(query, params).fetchall()]
        for item in result:
            if transaction_date := parse_calendar_date(item["transaction_date"]):
                item["transaction_date"] = transaction_date.isoformat()
        result.sort(
            key=lambda item: calendar_date_sort_key(item["transaction_date"], int(item["id"]))
        )
        return result

    def scoped_account_ids(self, account_type: str | None) -> list[int]:
        rows = self._connection.execute(
            """SELECT a.id
               FROM accounts a
               LEFT JOIN accounts parent ON parent.id = a.parent_account_id
               WHERE (a.parent_account_id IS NULL OR parent.balance_includes_children = 0)
                 AND (? IS NULL OR a.account_type = ?)""",
            (account_type, account_type),
        ).fetchall()
        return [int(row[0]) for row in rows]

    def balance_events(self) -> list[tuple[int, int, str, float]]:
        snapshot_rows = self._connection.execute(
            "SELECT id, account_id, snapshot_date, amount_cents FROM balance_snapshots"
        ).fetchall()
        transaction_rows = self._connection.execute(
            """SELECT id, account_id, transaction_date, balance_after_cents
               FROM transactions WHERE balance_after_cents IS NOT NULL"""
        ).fetchall()
        events = [
            (
                -int(row[0]),
                int(row[1]),
                canonical_date_or_stored(row[2]),
                float(from_cents(row[3])),
            )
            for row in snapshot_rows
        ] + [
            (
                int(row[0]),
                int(row[1]),
                canonical_date_or_stored(row[2]),
                float(from_cents(row[3])),
            )
            for row in transaction_rows
        ]
        events.sort(key=lambda item: balance_event_sort_key(item[2], item[0]))
        return events

    def first_snapshot_rows(
        self, account_id: int | None, account_type: str | None, include_children: bool
    ) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """SELECT a.id AS account_id, a.account_number, a.institution,
                      a.name AS account_name, a.asset_kind, a.parent_account_id,
                      parent.name AS parent_name,
                      parent.account_number AS parent_account_number,
                      parent.institution AS parent_institution,
                      parent.balance_includes_children AS parent_balance_includes_children,
                      s.id AS snapshot_id, s.snapshot_date,
                      s.amount_cents / 100.0 AS amount
               FROM accounts a
               LEFT JOIN accounts parent ON parent.id = a.parent_account_id
               JOIN balance_snapshots s ON s.account_id = a.id
               WHERE (? IS NULL OR a.id = ? OR (? = 1 AND a.parent_account_id = ?))
                 AND (? IS NULL OR a.account_type = ?)""",
            (
                account_id,
                account_id,
                int(include_children),
                account_id,
                account_type,
                account_type,
            ),
        ).fetchall()
        first_by_account: dict[int, dict[str, object]] = {}
        for stored_row in rows:
            row = dict(stored_row)
            row_account_id = int(cast(str | int, row["account_id"]))
            current = first_by_account.get(row_account_id)
            row_key = calendar_date_sort_key(
                row["snapshot_date"], int(cast(str | int, row["snapshot_id"]))
            )
            if current is None or row_key < calendar_date_sort_key(
                current["snapshot_date"], int(cast(str | int, current["snapshot_id"]))
            ):
                first_by_account[row_account_id] = row
        result = list(first_by_account.values())
        result.sort(
            key=lambda row: calendar_date_sort_key(
                row["snapshot_date"], int(cast(str | int, row["snapshot_id"]))
            ),
            reverse=True,
        )
        for row in result:
            del row["snapshot_id"]
        return result

    _SELECT = """SELECT id, account_id, raw_transaction_id, transaction_date,
                         amount_cents, description, balance_after_cents, category, transaction_type
                  FROM transactions"""

    _SUMMARY_SELECT = """
        SELECT t.id, t.transaction_date, t.amount_cents / 100.0 AS amount, t.description,
               t.balance_after_cents / 100.0 AS balance_after, t.category, t.transaction_type,
               a.id AS account_id, a.account_number, a.institution, a.name AS account_name,
               a.asset_kind, parent.name AS parent_name,
               parent.account_number AS parent_account_number,
               parent.institution AS parent_institution,
               parent.balance_includes_children AS parent_balance_includes_children
        FROM transactions t
        JOIN accounts a ON a.id = t.account_id
        LEFT JOIN accounts parent ON parent.id = a.parent_account_id
        __TRANSACTION_FILTER__
        ORDER BY t.transaction_date ASC, t.id ASC
        """

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> Transaction:
        transaction_id = row[0]
        account_id = row[1]
        if not isinstance(transaction_id, int) or not isinstance(account_id, int):
            raise TypeError("Transaction identifiers must be integers")
        return Transaction(
            id=transaction_id,
            account_id=account_id,
            raw_transaction_id=int(cast(str | int, row[2])) if row[2] is not None else None,
            transaction_date=str(row[3]),
            amount=float(from_cents(row[4])),
            description=str(row[5]) if row[5] is not None else None,
            balance_after=(float(from_cents(row[6])) if row[6] is not None else None),
            category=str(row[7]) if row[7] is not None else None,
            transaction_type=str(row[8]),
        )
