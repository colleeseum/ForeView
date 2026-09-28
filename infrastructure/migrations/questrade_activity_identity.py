from __future__ import annotations

import hashlib
import json
import sqlite3


class QuestradeActivityIdentityMigration:
    """Re-key stored Questrade activity to the login-independent identity.

    Activity used to be batched per login and account, with a row hash that
    included the login name. The sync now keeps one batch per Questrade account
    and hashes each activity's own content, so without this migration the first
    sync after upgrading would import every stored activity again.

    Where two logins stored the same activity for one account, the second copy
    is left in its original batch unchanged: that duplicate predates this
    migration, and deleting ledger rows automatically would be riskier.
    """

    version = 4
    name = "questrade_activity_identity"

    def apply(self, connection: sqlite3.Connection) -> None:
        legacy_batches = connection.execute(
            """SELECT id, file_hash FROM import_batches
               WHERE file_hash GLOB 'questrade:*:*:activities' ORDER BY id"""
        ).fetchall()
        for batch_id, file_hash in legacy_batches:
            _prefix, _login, account_number, _suffix = str(file_hash).split(":", 3)
            if ":" in account_number:  # not the legacy login:account form
                continue
            target_hash = f"questrade:{account_number}:activities"
            target = connection.execute(
                "SELECT id FROM import_batches WHERE file_hash = ?", (target_hash,)
            ).fetchone()
            if target is None:
                connection.execute(
                    "UPDATE import_batches SET file_hash = ? WHERE id = ?", (target_hash, batch_id)
                )
                target_id = int(batch_id)
            else:
                target_id = int(target[0])
            self._rekey_rows(connection, int(batch_id), target_id)
            self._refresh_row_count(connection, target_id)
            remaining = connection.execute(
                "SELECT COUNT(*) FROM raw_transactions WHERE batch_id = ?", (batch_id,)
            ).fetchone()[0]
            if batch_id != target_id and remaining == 0:
                connection.execute("DELETE FROM import_batches WHERE id = ?", (batch_id,))
            elif batch_id != target_id:
                self._refresh_row_count(connection, int(batch_id))

    @staticmethod
    def _rekey_rows(connection: sqlite3.Connection, batch_id: int, target_id: int) -> None:
        rows = connection.execute(
            "SELECT id, raw_data FROM raw_transactions WHERE batch_id = ? ORDER BY row_number, id",
            (batch_id,),
        ).fetchall()
        for raw_id, raw_data in rows:
            activity = json.loads(str(raw_data)).get("activity")
            if activity is None:
                continue
            # Must match the hash the sync computes for an activity.
            row_hash = hashlib.sha256(json.dumps(activity, sort_keys=True).encode()).hexdigest()
            clash = connection.execute(
                "SELECT 1 FROM raw_transactions WHERE batch_id = ? AND row_hash = ? AND id != ?",
                (target_id, row_hash, raw_id),
            ).fetchone()
            if clash:
                continue
            if batch_id == target_id:
                connection.execute(
                    "UPDATE raw_transactions SET row_hash = ? WHERE id = ?", (row_hash, raw_id)
                )
                continue
            next_row = connection.execute(
                "SELECT COALESCE(MAX(row_number), 0) + 1 FROM raw_transactions WHERE batch_id = ?",
                (target_id,),
            ).fetchone()[0]
            connection.execute(
                "UPDATE raw_transactions SET batch_id = ?, row_number = ?, row_hash = ? WHERE id = ?",
                (target_id, next_row, row_hash, raw_id),
            )

    @staticmethod
    def _refresh_row_count(connection: sqlite3.Connection, batch_id: int) -> None:
        connection.execute(
            """UPDATE import_batches SET row_count = (
                   SELECT COUNT(*) FROM transactions t
                   JOIN raw_transactions r ON r.id = t.raw_transaction_id
                   WHERE r.batch_id = ?
               ) WHERE id = ?""",
            (batch_id, batch_id),
        )
