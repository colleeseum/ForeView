from __future__ import annotations

import sqlite3


class QuestradeSyncStatusMigration:
    """Separate synchronization attempts, successes, and failure details."""

    version = 2
    name = "questrade_sync_status"

    def apply(self, connection: sqlite3.Connection) -> None:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(questrade_authorizations)")
        }
        for column in ("last_sync_at", "last_sync_attempt_at", "last_sync_error"):
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE questrade_authorizations ADD COLUMN {column} TEXT"  # noqa: S608
                )
