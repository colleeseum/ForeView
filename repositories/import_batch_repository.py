# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.import_batch import ImportBatch


class ImportBatchRepository:
    """Persist and retrieve import-batch identity and progress."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        account_id: int | None,
        filename: str,
        file_hash: str,
        row_count: int = 0,
    ) -> ImportBatch:
        cursor = self._connection.execute(
            """INSERT INTO import_batches(account_id, filename, file_hash, row_count)
               VALUES (?, ?, ?, ?)""",
            (account_id, filename, file_hash, row_count),
        )
        batch = self.get(cursor.lastrowid)
        if batch is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created import batch could not be retrieved")
        return batch

    def get_or_create(
        self,
        account_id: int | None,
        filename: str,
        file_hash: str,
        row_count: int = 0,
    ) -> ImportBatch:
        self._connection.execute(
            """INSERT OR IGNORE INTO import_batches(account_id, filename, file_hash, row_count)
               VALUES (?, ?, ?, ?)""",
            (account_id, filename, file_hash, row_count),
        )
        batch = self.get_by_hash(file_hash)
        if batch is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Import batch could not be retrieved")
        return batch

    def history(
        self,
        account_id: int | None = None,
        account_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        """Recent import batches with their account and reconciliation outcome."""
        filters = []
        params: list[object] = []
        if account_id is not None:
            filters.append("b.account_id = ?")
            params.append(account_id)
        if account_type is not None:
            filters.append("a.account_type = ?")
            params.append(account_type)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        sql_template = """
            SELECT b.id, b.filename, b.imported_at, b.row_count,
                   a.account_number, a.institution,
                   r.status AS reconciliation_status, r.statement_start, r.statement_end,
                   r.difference
            FROM import_batches b
            LEFT JOIN accounts a ON a.id = b.account_id
            LEFT JOIN statement_reconciliations r ON r.import_batch_id = b.id
            __IMPORT_FILTER__
            ORDER BY b.imported_at DESC, b.id DESC
            LIMIT ?
            """
        query = sql_template.replace("__IMPORT_FILTER__", where)
        rows = self._connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get(self, batch_id: int | None) -> ImportBatch | None:
        if batch_id is None:
            return None
        row = self._connection.execute(
            """SELECT id, account_id, filename, file_hash, imported_at, row_count
               FROM import_batches WHERE id = ?""",
            (batch_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def get_by_hash(self, file_hash: str) -> ImportBatch | None:
        row = self._connection.execute(
            """SELECT id, account_id, filename, file_hash, imported_at, row_count
               FROM import_batches WHERE file_hash = ?""",
            (file_hash,),
        ).fetchone()
        return self._from_row(row) if row else None

    def update_row_count(self, batch_id: int, row_count: int) -> None:
        self._connection.execute(
            "UPDATE import_batches SET row_count = ? WHERE id = ?",
            (row_count, batch_id),
        )

    def update_row_count_from_transactions(self, batch_id: int) -> None:
        self._connection.execute(
            """UPDATE import_batches SET row_count = (
                   SELECT COUNT(*) FROM transactions t
                   JOIN raw_transactions r ON r.id = t.raw_transaction_id
                   WHERE r.batch_id = ?
               ) WHERE id = ?""",
            (batch_id, batch_id),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> ImportBatch:
        batch_id = row[0]
        account_id = row[1]
        row_count = row[5]
        if not isinstance(batch_id, int):
            raise TypeError("Import batch id must be an integer")
        if account_id is not None and not isinstance(account_id, int):
            raise TypeError("Import batch account id must be an integer")
        if not isinstance(row_count, int):
            raise TypeError("Import batch row count must be an integer")
        return ImportBatch(
            id=batch_id,
            account_id=account_id,
            filename=str(row[2]),
            file_hash=str(row[3]),
            imported_at=str(row[4]),
            row_count=row_count,
        )
