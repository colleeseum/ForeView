# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import app as application
from infrastructure.migrations.annual_employment_province_backfill import (
    AnnualEmploymentProvinceBackfillMigration,
)
from infrastructure.migrations.correction_revision_history import (
    CorrectionRevisionHistoryMigration,
)
from infrastructure.migrations.corrections_table import CorrectionsTableMigration
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
                    (7, "annual_employment_province"),
                    (8, "annual_employment_province_backfill"),
                    (9, "household_expenses"),
                    (10, "tax_and_public_pension_records"),
                    (11, "annual_tax_values"),
                    (12, "corrections_table"),
                    (13, "correction_revision_history"),
                    (14, "factual_expenses"),
                ],
            )

    def test_correction_history_migration_preserves_active_and_removed_rows(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE TABLE people(id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("INSERT INTO people(id, name) VALUES (1, 'Example')")
        CorrectionsTableMigration().apply(connection)
        values = (
            1,
            2025,
            "employment_income",
            11000000,
            "Supporting records",
            "return",
            "CA",
            "employment_income",
            "Employment income",
            10000000,
            "UFile T1",
            "2026.09.29",
            "document-hash",
            "fingerprint",
        )
        connection.execute(
            """INSERT INTO corrections(
                   person_id, tax_year, concept, correct_amount_cents, reason,
                   source_at_correction_document_kind,
                   source_at_correction_jurisdiction,
                   source_at_correction_concept,
                   source_at_correction_description,
                   source_at_correction_reported_amount_cents,
                   source_at_correction_source,
                   source_at_correction_source_version,
                   source_at_correction_document_hash, fingerprint
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
        connection.execute(
            """INSERT INTO corrections(
                   person_id, tax_year, concept, correct_amount_cents, reason,
                   source_at_correction_document_kind,
                   source_at_correction_jurisdiction,
                   source_at_correction_concept,
                   source_at_correction_description,
                   source_at_correction_reported_amount_cents,
                   source_at_correction_source,
                   source_at_correction_source_version,
                   source_at_correction_document_hash, fingerprint, deleted_at
               ) VALUES (?, ?, 'interest_investment_income', ?, ?, ?, ?,
                         'interest_investment_income', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                values[0],
                values[1],
                300000,
                values[4],
                values[5],
                values[6],
                "Interest income",
                250000,
                values[10],
                values[11],
                values[12],
                values[13],
            ),
        )

        CorrectionRevisionHistoryMigration().apply(connection)

        rows = connection.execute(
            """SELECT concept, revision_number, revision_kind, correct_amount_cents
                 FROM corrections
                ORDER BY concept, revision_number"""
        ).fetchall()
        self.assertEqual(
            rows,
            [
                ("employment_income", 1, "create", 11000000),
                ("interest_investment_income", 1, "create", 300000),
                ("interest_investment_income", 2, "remove", 300000),
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
                    "household_expense_plans",
                    "expense_categories",
                    "expense_records",
                }.issubset(tables)
            )
            with runtime.connect() as connection:
                columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(annual_employment_actuals)")
                }
            self.assertIn("bonus_cents", columns)
            self.assertIn("province_of_employment", columns)
            self.assertIn("province_of_residence", columns)
            self.assertIn("payroll_plan", columns)
            with runtime.connect() as connection:
                tax_value_columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(annual_tax_values)")
                }
            self.assertIn("concept", tax_value_columns)
            self.assertIn("determined_amount_cents", tax_value_columns)

    def test_legacy_income_province_uses_nearest_known_employment_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeConfig(Path(directory))
            application.initialize(runtime)
            with runtime.connect() as connection:
                person_id = connection.execute(
                    "INSERT INTO people(name) VALUES ('Example')"
                ).lastrowid
                connection.execute(
                    """INSERT INTO employment_baselines(
                           person_id, effective_date, annual_salary_cents,
                           province_of_employment, payroll_plan
                       ) VALUES (?, '2026-01-01', 10000000, 'ON', 'CPP')""",
                    (person_id,),
                )
                connection.execute(
                    """INSERT INTO annual_employment_actuals(
                           person_id, tax_year, salary_income_cents
                       ) VALUES (?, 2025, 9500000)""",
                    (person_id,),
                )

                AnnualEmploymentProvinceBackfillMigration().apply(connection)

                province = connection.execute(
                    "SELECT province_of_employment FROM annual_employment_actuals"
                ).fetchone()[0]
            self.assertEqual(province, "ON")

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
