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
from infrastructure.migrations.expense_identities import ExpenseIdentitiesMigration
from infrastructure.migrations.factual_expense_schema_upgrade import (
    FactualExpenseSchemaUpgradeMigration,
)
from infrastructure.migrations.factual_expenses import create_expense_records_table
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
                    (15, "factual_expense_schema_upgrade"),
                    (16, "expense_identities"),
                    (17, "expense_period_kind"),
                ],
            )

    def test_expense_identity_migration_backfills_existing_records(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE TABLE import_batches(id INTEGER PRIMARY KEY)")
        connection.execute(
            """CREATE TABLE expense_categories(
                   id INTEGER PRIMARY KEY,
                   name TEXT NOT NULL,
                   classification TEXT NOT NULL,
                   is_active INTEGER NOT NULL DEFAULT 1,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        connection.execute(
            "INSERT INTO expense_categories(id, name, classification) VALUES (1, 'Utilities', 'required')"
        )
        create_expense_records_table(connection)
        connection.executemany(
            """INSERT INTO expense_records(
                   name, category_id, category_name, classification, amount_cents,
                   period_start, period_end, source_kind, association_kind, overlap_status
               ) VALUES (?, 1, 'Utilities', 'required', 10000, ?, ?, 'manual', 'household', ?)""",
            (
                ("Hydro", "2025-01-01", "2025-01-31", "clear"),
                ("Hydro", "2025-01-15", "2025-02-28", "clear"),
                ("Energir", "2025-01-01", "2025-01-31", "potential"),
            ),
        )

        ExpenseIdentitiesMigration().apply(connection)

        identities = connection.execute(
            "SELECT name FROM expense_identities ORDER BY name"
        ).fetchall()
        record_identities = connection.execute(
            "SELECT name, identity_id, overlap_status FROM expense_records ORDER BY id"
        ).fetchall()
        assert identities == [("Energir",), ("Hydro",)]
        assert record_identities[0][1] == record_identities[1][1]
        assert record_identities[0][1] != record_identities[2][1]
        assert [row[2] for row in record_identities] == ["potential", "potential", "clear"]

    def test_factual_expense_upgrade_preserves_draft_migration_records(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE TABLE import_batches(id INTEGER PRIMARY KEY)")
        connection.execute(
            """CREATE TABLE expense_categories(
                   id INTEGER PRIMARY KEY,
                   name TEXT NOT NULL,
                   classification TEXT NOT NULL,
                   is_active INTEGER NOT NULL DEFAULT 1,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        connection.execute(
            """CREATE TABLE expense_records(
                   id INTEGER PRIMARY KEY,
                   name TEXT NOT NULL,
                   category_id INTEGER NOT NULL,
                   amount_cents INTEGER NOT NULL,
                   period_start TEXT NOT NULL,
                   period_end TEXT NOT NULL,
                   source_kind TEXT NOT NULL,
                   source_document_id INTEGER,
                   association_kind TEXT NOT NULL,
                   association_id INTEGER,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        connection.execute(
            "INSERT INTO expense_categories(id, name, classification) VALUES (1, 'Utilities', 'required')"
        )
        connection.execute(
            """INSERT INTO expense_records(
                   id, name, category_id, amount_cents, period_start, period_end,
                   source_kind, association_kind
               ) VALUES (1, 'Hydro', 1, 10000, '2026-01-01', '2026-01-31',
                         'manual', 'household')"""
        )

        FactualExpenseSchemaUpgradeMigration().apply(connection)

        record = connection.execute(
            """SELECT category_name, classification, overlap_status, updated_at
                 FROM expense_records WHERE id = 1"""
        ).fetchone()
        self.assertEqual(tuple(record[:3]), ("Utilities", "required", "clear"))
        self.assertIsNotNone(record[3])
        foreign_tables = {
            str(row[2]) for row in connection.execute("PRAGMA foreign_key_list(expense_records)")
        }
        self.assertIn("import_batches", foreign_tables)

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
