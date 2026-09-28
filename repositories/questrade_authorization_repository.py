from __future__ import annotations

import sqlite3

from domain.questrade_authorization import QuestradeAuthorization


class QuestradeAuthorizationRepository:
    """Persist encrypted Questrade OAuth tokens, one row per named connection."""

    _SELECT = """SELECT id, name, access_token, refresh_token, api_server, access_expires_at,
                        refresh_expires_at, last_sync_attempt_at, last_sync_at,
                        last_sync_error, updated_at
                 FROM questrade_authorizations"""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_all(self) -> list[QuestradeAuthorization]:
        rows = self._connection.execute(f"{self._SELECT} ORDER BY name").fetchall()  # noqa: S608
        return [self._from_row(row) for row in rows]

    def get_by_name(self, name: str) -> QuestradeAuthorization | None:
        row = self._connection.execute(
            f"{self._SELECT} WHERE name = ?",  # noqa: S608
            (name,),
        ).fetchone()
        return self._from_row(row) if row else None

    def save_tokens(
        self,
        name: str,
        *,
        access_token: str,
        refresh_token: str,
        api_server: str,
        access_expires_at: str | None,
        refresh_expires_at: str | None,
    ) -> None:
        """Store newly issued tokens for a connection, replacing any it already has."""
        self._connection.execute(
            """INSERT INTO questrade_authorizations(
               name, access_token, refresh_token, api_server,
               access_expires_at, refresh_expires_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(name) DO UPDATE SET
               access_token=excluded.access_token,
               refresh_token=excluded.refresh_token,
               api_server=excluded.api_server,
               access_expires_at=excluded.access_expires_at,
               refresh_expires_at=excluded.refresh_expires_at,
               updated_at=CURRENT_TIMESTAMP""",
            (name, access_token, refresh_token, api_server, access_expires_at, refresh_expires_at),
        )

    def update_tokens(
        self,
        authorization_id: int,
        *,
        access_token: str,
        refresh_token: str,
        api_server: str,
        access_expires_at: str | None,
        refresh_expires_at: str | None,
    ) -> None:
        self._connection.execute(
            """UPDATE questrade_authorizations
               SET access_token = ?, refresh_token = ?, api_server = ?,
                   access_expires_at = ?, refresh_expires_at = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                access_token,
                refresh_token,
                api_server,
                access_expires_at,
                refresh_expires_at,
                authorization_id,
            ),
        )

    def add_if_absent(
        self, name: str, *, access_token: str, refresh_token: str, api_server: str
    ) -> None:
        self._connection.execute(
            """INSERT INTO questrade_authorizations(
                   name, access_token, refresh_token, api_server, access_expires_at
               ) VALUES (?, ?, ?, ?, NULL)
               ON CONFLICT(name) DO NOTHING""",
            (name, access_token, refresh_token, api_server),
        )

    def mark_attempted(self, name: str, attempted_at: str) -> None:
        self._connection.execute(
            """UPDATE questrade_authorizations
               SET last_sync_attempt_at = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?""",
            (attempted_at, name),
        )

    def mark_synced(self, name: str, synced_at: str) -> None:
        self._connection.execute(
            """UPDATE questrade_authorizations
               SET last_sync_attempt_at = ?, last_sync_at = ?, last_sync_error = NULL,
                   updated_at = CURRENT_TIMESTAMP WHERE name = ?""",
            (synced_at, synced_at, name),
        )

    def mark_failed(self, name: str, attempted_at: str, error: str) -> None:
        self._connection.execute(
            """UPDATE questrade_authorizations
               SET last_sync_attempt_at = ?, last_sync_error = ?, updated_at = CURRENT_TIMESTAMP
               WHERE name = ?""",
            (attempted_at, error, name),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> QuestradeAuthorization:
        def optional(value: object) -> str | None:
            return None if value is None else str(value)

        return QuestradeAuthorization(
            id=int(str(row[0])),
            name=str(row[1]),
            access_token=str(row[2]),
            refresh_token=str(row[3]),
            api_server=str(row[4]),
            access_expires_at=optional(row[5]),
            refresh_expires_at=optional(row[6]),
            last_sync_attempt_at=optional(row[7]),
            last_sync_at=optional(row[8]),
            last_sync_error=optional(row[9]),
            updated_at=optional(row[10]),
        )
