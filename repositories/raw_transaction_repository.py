from __future__ import annotations

import sqlite3

from domain.raw_transaction import RawTransaction


class RawTransactionRepository:
    """Persist original import rows without interpreting their financial meaning."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add_if_new(
        self, batch_id: int, row_number: int, row_hash: str, raw_data: str
    ) -> RawTransaction | None:
        cursor = self._connection.execute(
            """INSERT OR IGNORE INTO raw_transactions(
                   batch_id, row_number, row_hash, raw_data
               ) VALUES (?, ?, ?, ?)""",
            (batch_id, row_number, row_hash, raw_data),
        )
        return self.get(cursor.lastrowid) if cursor.rowcount else None

    def next_row_number(self, batch_id: int) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(row_number), 0) + 1 FROM raw_transactions WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        return int(row[0])

    def id_for_hash(self, batch_id: int, row_hash: str) -> int | None:
        row = self._connection.execute(
            "SELECT id FROM raw_transactions WHERE batch_id = ? AND row_hash = ?",
            (batch_id, row_hash),
        ).fetchone()
        return int(row[0]) if row else None

    def add(self, batch_id: int, row_number: int, row_hash: str, raw_data: str) -> int:
        cursor = self._connection.execute(
            """INSERT INTO raw_transactions(batch_id, row_number, row_hash, raw_data)
               VALUES (?, ?, ?, ?)""",
            (batch_id, row_number, row_hash, raw_data),
        )
        if cursor.lastrowid is None:  # pragma: no cover - SQLite insert invariant
            raise RuntimeError("Created raw transaction has no identifier")
        return cursor.lastrowid

    def get(self, raw_transaction_id: int | None) -> RawTransaction | None:
        if raw_transaction_id is None:
            return None
        row = self._connection.execute(
            """SELECT id, batch_id, row_number, row_hash, raw_data
               FROM raw_transactions WHERE id = ?""",
            (raw_transaction_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_batch(self, batch_id: int) -> list[RawTransaction]:
        rows = self._connection.execute(
            """SELECT id, batch_id, row_number, row_hash, raw_data
               FROM raw_transactions WHERE batch_id = ? ORDER BY row_number, id""",
            (batch_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> RawTransaction:
        raw_id, batch_id, row_number = row[0], row[1], row[2]
        if (
            not isinstance(raw_id, int)
            or not isinstance(batch_id, int)
            or not isinstance(row_number, int)
        ):
            raise TypeError("Raw transaction identifiers and row number must be integers")
        return RawTransaction(
            id=raw_id,
            batch_id=batch_id,
            row_number=row_number,
            row_hash=str(row[3]),
            raw_data=str(row[4]),
        )
