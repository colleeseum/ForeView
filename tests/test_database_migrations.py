from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import app as application
from infrastructure.runtime_config import RuntimeConfig


class DatabaseMigrationTests(unittest.TestCase):
    def test_initialization_records_ordered_migrations_once(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeConfig(Path(directory))

            application.initialize(runtime)
            application.initialize(runtime)

            with runtime.connect() as connection:
                migrations = connection.execute(
                    "SELECT version, name FROM schema_migrations ORDER BY version"
                ).fetchall()
            self.assertEqual(
                [tuple(row) for row in migrations],
                [
                    (1, "baseline_domain_schema"),
                    (2, "questrade_sync_status"),
                    (3, "monetary_cents"),
                    (4, "questrade_activity_identity"),
                    (5, "employment_projection"),
                    (6, "employment_income_records"),
                ],
            )

    def test_employment_projection_migration_creates_typed_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeConfig(Path(directory))
            application.initialize(runtime)

            with runtime.connect() as connection:
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }

            self.assertTrue(
                {
                    "employment_baselines",
                    "annual_employment_actuals",
                    "employment_projection_settings",
                    "employment_projection_overrides",
                }.issubset(tables)
            )
            with runtime.connect() as connection:
                columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(annual_employment_actuals)")
                }
            self.assertIn("bonus_cents", columns)

    def test_monetary_migration_backfills_and_tracks_legacy_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeConfig(Path(directory))
            application.initialize(runtime)
            with runtime.connect() as connection:
                account_id = connection.execute(
                    "INSERT INTO accounts(name, account_type) VALUES ('Test', 'non_registered')"
                ).lastrowid
                transaction_id = connection.execute(
                    """INSERT INTO transactions(account_id, transaction_date, amount)
                       VALUES (?, '2026-01-01', 12.345)""",
                    (account_id,),
                ).lastrowid
                cents = connection.execute(
                    "SELECT amount_cents FROM transactions WHERE id = ?", (transaction_id,)
                ).fetchone()[0]
                connection.execute(
                    "UPDATE transactions SET amount = -1.005 WHERE id = ?", (transaction_id,)
                )
                updated_cents = connection.execute(
                    "SELECT amount_cents FROM transactions WHERE id = ?", (transaction_id,)
                ).fetchone()[0]

            self.assertEqual(cents, 1235)
            self.assertEqual(updated_cents, -101)

    def test_legacy_questrade_table_is_upgraded_by_versioned_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeConfig(Path(directory))
            runtime.data_dir.mkdir(exist_ok=True)
            with closing(sqlite3.connect(runtime.database_path)) as connection:
                connection.execute(
                    """CREATE TABLE questrade_authorizations (
                           id INTEGER PRIMARY KEY,
                           name TEXT NOT NULL UNIQUE,
                           access_token TEXT NOT NULL,
                           refresh_token TEXT NOT NULL,
                           api_server TEXT NOT NULL
                    )"""
                )
                connection.commit()

            application.initialize(runtime)

            with runtime.connect() as connection:
                columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(questrade_authorizations)")
                }
            self.assertTrue(
                {"last_sync_at", "last_sync_attempt_at", "last_sync_error"}.issubset(columns)
            )


if __name__ == "__main__":
    unittest.main()
