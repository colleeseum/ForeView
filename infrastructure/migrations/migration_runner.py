from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from .migration import Migration


class MigrationRunner:
    """Apply each registered migration once and retain an auditable ledger."""

    def __init__(self, connection: sqlite3.Connection, migrations: Iterable[Migration]) -> None:
        self._connection = connection
        self._migrations = tuple(sorted(migrations, key=lambda migration: migration.version))

    def apply(self) -> None:
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version INTEGER PRIMARY KEY,
                   name TEXT NOT NULL UNIQUE,
                   applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        applied = {
            int(row[0]): str(row[1])
            for row in self._connection.execute("SELECT version, name FROM schema_migrations")
        }
        for migration in self._migrations:
            recorded_name = applied.get(migration.version)
            if recorded_name is not None:
                if recorded_name != migration.name:
                    raise RuntimeError(
                        f"Migration {migration.version} is recorded as {recorded_name!r}, "
                        f"not {migration.name!r}"
                    )
                continue
            migration.apply(self._connection)
            self._connection.execute(
                "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                (migration.version, migration.name),
            )
            self._connection.commit()
