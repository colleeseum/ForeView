from __future__ import annotations

import sqlite3
from datetime import datetime


class ActivitySyncStateRepository:
    """Remember, per connected account, the time up to which activity was fetched."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def synced_until(self, account_id: int) -> datetime | None:
        row = self._connection.execute(
            "SELECT synced_until FROM activity_sync_state WHERE account_id = ?", (account_id,)
        ).fetchone()
        return datetime.fromisoformat(str(row[0])) if row else None

    def record(self, account_id: int, synced_until: datetime) -> None:
        self._connection.execute(
            """INSERT INTO activity_sync_state(account_id, synced_until) VALUES (?, ?)
               ON CONFLICT(account_id) DO UPDATE SET synced_until = excluded.synced_until""",
            (account_id, synced_until.isoformat()),
        )
