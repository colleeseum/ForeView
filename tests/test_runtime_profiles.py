# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import app as application
from infrastructure.runtime_config import RuntimeConfig
from synthetic_expenses import load_synthetic_expenses
from synthetic_questrade import load_synthetic_questrade
from synthetic_runtime import create_synthetic_runtime


class RuntimeProfileTests(unittest.TestCase):
    def test_application_startup_migrates_legacy_database_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "legacy-runtime"
            runtime.mkdir()
            (runtime / "finance.config.json").write_text(
                json.dumps({"RUNTIME_ENVIRONMENT": "synthetic"})
            )
            database = runtime / "finance.sqlite3"
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE people (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE accounts (
                        id INTEGER PRIMARY KEY,
                        owner_id INTEGER,
                        name TEXT,
                        account_type TEXT NOT NULL
                    );
                    CREATE TABLE fixed_term_deposits (
                        id INTEGER PRIMARY KEY,
                        account_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        principal REAL NOT NULL,
                        interest_rate REAL NOT NULL,
                        start_date TEXT NOT NULL,
                        maturity_date TEXT NOT NULL,
                        redeemable INTEGER NOT NULL DEFAULT 0,
                        renewal_rule TEXT NOT NULL DEFAULT 'cash_at_maturity'
                    );
                    CREATE TABLE import_batches (
                        id INTEGER PRIMARY KEY,
                        filename TEXT NOT NULL,
                        file_hash TEXT NOT NULL UNIQUE,
                        imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        row_count INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE TABLE questrade_authorizations (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        access_token TEXT NOT NULL,
                        refresh_token TEXT NOT NULL,
                        api_server TEXT NOT NULL,
                        access_expires_at TEXT,
                        refresh_expires_at TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    INSERT INTO people(id, name) VALUES (1, 'Legacy Owner');
                    INSERT INTO accounts(id, owner_id, name, account_type)
                    VALUES (1, 1, 'Legacy TFSA', 'tfsa');
                    INSERT INTO fixed_term_deposits(
                        account_id, name, principal, interest_rate,
                        start_date, maturity_date
                    ) VALUES (1, 'Legacy GIC #12345', 10000, 0.04,
                              '2026-01-01', '2027-01-01');
                    """
                )

            runtime_config = RuntimeConfig.load(runtime)
            application.initialize(runtime_config)
            application.initialize(runtime_config)
            client = application.create_app(runtime_config).test_client()
            response = client.get("/api/model/accounts")
            self.assertEqual(response.status_code, 200)
            accounts = response.get_json()["accounts"]
            parent = next(item for item in accounts if item["name"] == "Legacy TFSA")
            child = next(item for item in accounts if item["name"] == "Legacy GIC #12345")
            self.assertEqual(child["parent_account_id"], parent["id"])
            self.assertEqual(child["principal"], 10000)
            self.assertIn("Legacy Owner", parent["owners"])
            self.assertIn("Legacy Owner", child["owners"])
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM accounts WHERE asset_kind = 'gic'"
                    ).fetchone()[0],
                    1,
                )
                self.assertTrue(
                    {"last_sync_at", "last_sync_attempt_at", "last_sync_error"}.issubset(
                        {
                            row[1]
                            for row in connection.execute(
                                "PRAGMA table_info(questrade_authorizations)"
                            )
                        }
                    )
                )
                self.assertIn(
                    "account_id",
                    {row[1] for row in connection.execute("PRAGMA table_info(import_batches)")},
                )

    def test_synthetic_questrade_loader_populates_dev_runtime_and_rejects_private_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "synthetic"
            database, _ = create_synthetic_runtime(runtime)
            results = load_synthetic_questrade(runtime)
            self.assertEqual(sum(item["account_count"] for item in results), 4)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    connection.execute(
                        """SELECT COUNT(*) FROM accounts
                           WHERE external_provider = 'questrade'"""
                    ).fetchone()[0],
                    4,
                )
                self.assertEqual(
                    connection.execute(
                        """SELECT COUNT(*) FROM account_owners ao
                           JOIN accounts a ON a.id = ao.account_id
                           WHERE a.external_provider = 'questrade'"""
                    ).fetchone()[0],
                    4,
                )
            repeated = load_synthetic_questrade(runtime)
            self.assertEqual(sum(item["transaction_count"] for item in repeated), 0)

            private_runtime = root / "private"
            private_runtime.mkdir()
            (private_runtime / "finance.config.json").write_text(
                json.dumps({"RUNTIME_ENVIRONMENT": "private"})
            )
            with self.assertRaisesRegex(RuntimeError, "non-synthetic runtime"):
                load_synthetic_questrade(private_runtime)

    def test_synthetic_runtime_is_isolated_and_serves_integration_data(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            database, config = create_synthetic_runtime(runtime)
            self.assertEqual(database.parent, runtime.resolve())
            self.assertEqual(json.loads(config.read_text())["RUNTIME_ENVIRONMENT"], "synthetic")

            runtime_config = RuntimeConfig.load(runtime)
            application.initialize(runtime_config)
            with application.create_app(runtime_config).test_client() as client:
                accounts_response = client.get("/api/model/accounts")
                dashboard_response = client.get("/api/dashboard")
                real_estate_response = client.get("/api/model/real-estate")
                transactions_response = client.get(
                    "/api/model/transactions?account_type=non_registered"
                )
                salary_response = client.get("/api/salary-projection?start_year=2026&end_year=2027")
                expenses_response = client.get("/expenses?year=2026")
            self.assertEqual(accounts_response.status_code, 200)
            self.assertEqual(dashboard_response.status_code, 200)
            self.assertEqual(real_estate_response.status_code, 200)
            self.assertEqual(transactions_response.status_code, 200)
            self.assertEqual(salary_response.status_code, 200)
            self.assertEqual(expenses_response.status_code, 200)
            self.assertIn(b"Hydro", expenses_response.data)
            self.assertIn(b"Energir", expenses_response.data)
            self.assertIn(b"Montreal property tax", expenses_response.data)
            self.assertIn(b"$4293.00", expenses_response.data)
            self.assertIn(b"$5295.00", expenses_response.data)
            accounts = accounts_response.get_json()["accounts"]
            account_totals = {
                item["type"]: item for item in accounts_response.get_json()["category_totals"]
            }
            accounts_by_number = {item["account_number"]: item for item in accounts}
            self.assertEqual(accounts_by_number["SYN-SAV-001"]["latest_amount"], 24500)
            self.assertEqual(accounts_by_number["SYN-CALC-001"]["latest_amount"], 5000)
            self.assertEqual(accounts_by_number["SYN-RESP-001"]["latest_amount"], 28750)
            self.assertEqual(
                accounts_by_number["SYN-RESP-001"]["name"],
                "Synthetic RESP · education savings",
            )
            self.assertEqual(accounts_by_number["99900011122233"]["latest_amount"], 90000)
            self.assertEqual(
                accounts_by_number["SYN-SAV-001"]["name"],
                "Generic CSV · supplied balances",
            )
            self.assertEqual(
                accounts_by_number["SYN-CALC-001"]["name"],
                "Generic CSV · reconstructed balances",
            )
            self.assertEqual(accounts_by_number["99900011122233"]["name"], "PDF statement + TR")
            maturity_notice_gic = next(
                item for number, item in accounts_by_number.items() if number.endswith(":900000002")
            )
            self.assertEqual(maturity_notice_gic["latest_amount"], 5000)
            self.assertIsNone(accounts_by_number["SYN-ACH-001"]["latest_amount"])
            self.assertEqual(accounts_by_number["SYN-ACH-001"]["rollup_amount"], 10450)
            self.assertEqual(accounts_by_number["SYN-ACH-001"]["non_gic_amount"], 0)
            self.assertEqual(accounts_by_number["999888777"]["latest_amount"], 107.5)
            self.assertEqual(accounts_by_number["999888777"]["rollup_amount"], 15557.5)
            self.assertEqual(accounts_by_number["999888777"]["non_gic_amount"], 107.5)
            self.assertEqual(accounts_by_number["SYN-TFSA-CONSOLIDATED"]["rollup_amount"], 50000)
            self.assertEqual(accounts_by_number["SYN-TFSA-CONSOLIDATED"]["non_gic_amount"], 39750)
            self.assertEqual(account_totals["tfsa"]["total"], 178607.5)
            self.assertEqual(account_totals["tfsa"]["count"], 4)
            self.assertEqual(account_totals["tfsa"]["gic_count"], 5)
            self.assertEqual(account_totals["resp"]["total"], 28750)
            self.assertEqual(account_totals["resp"]["count"], 1)
            dashboard = dashboard_response.get_json()
            category_totals = {item["type"]: item["total"] for item in dashboard["categories"]}
            self.assertEqual(category_totals["non_registered"], 31652.5)
            self.assertEqual(category_totals["tfsa"], 178607.5)
            self.assertEqual(category_totals["rrsp"], 315000)
            self.assertEqual(category_totals["resp"], 28750)
            self.assertEqual(dashboard["gic_value"], 56750)
            self.assertEqual(dashboard["immovable_value"], 610000)
            land = next(
                item
                for item in real_estate_response.get_json()["assets"]
                if item["name"] == "Land · non-principal property"
            )
            self.assertEqual(land["property_type"], "Vacant land")
            self.assertEqual(land["estimated_value"], 85000)
            self.assertEqual(land["acb"], 30000)
            self.assertFalse(land["principal_residence"])
            self.assertEqual(land["owners"][0]["name"], "Alex Example")
            transactions = transactions_response.get_json()["transactions"]
            self.assertEqual(transactions[0]["combined_balance_after"], 31652.5)
            salary_projection = salary_response.get_json()
            selected_scenario = next(
                scenario
                for scenario in salary_projection["scenarios"]
                if scenario["id"] == salary_projection["selected_scenario_id"]
            )
            self.assertEqual(selected_scenario["name"], "Synthetic salary baseline")
            self.assertEqual(len(salary_projection["people"]), 2)
            self.assertEqual(
                {person["name"] for person in salary_projection["people"]},
                {"Alex Example", "Jordan Example"},
            )
            people_by_name = {person["name"]: person for person in salary_projection["people"]}
            self.assertEqual(
                people_by_name["Alex Example"]["salary_anchor"]["annual_salary_rate"],
                "101500.00",
            )
            self.assertEqual(
                people_by_name["Jordan Example"]["salary_anchor"]["annual_salary_rate"],
                "80000.00",
            )
            household_2026 = next(
                year for year in salary_projection["household"] if year["year"] == 2026
            )
            self.assertEqual(household_2026["salary_income"], "186545.00")
            self.assertGreater(float(household_2026["disposable_income"]), 0)

            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM people").fetchone()[0], 2)
                calculated_balances = [
                    row[0]
                    for row in connection.execute(
                        """SELECT t.balance_after FROM transactions t
                           JOIN accounts a ON a.id = t.account_id
                           WHERE a.account_number = 'SYN-CALC-001'
                           ORDER BY t.transaction_date"""
                    )
                ]
                self.assertEqual(calculated_balances, [4975, 4950, 5000])
                statement_holdings = connection.execute(
                    """SELECT COUNT(*), SUM(h.market_value)
                       FROM investment_holdings h JOIN accounts a ON a.id = h.account_id
                       WHERE a.account_number = '99900011122233'"""
                ).fetchone()
                self.assertEqual(statement_holdings, (3, 90000))
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0], 12
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM expense_records").fetchone()[0], 3
                )

            self.assertEqual(load_synthetic_expenses(runtime), 0)

    def test_synthetic_runtime_refuses_to_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            create_synthetic_runtime(runtime)
            with self.assertRaises(FileExistsError):
                create_synthetic_runtime(runtime)

    def test_synthetic_expense_loader_refuses_private_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            runtime.mkdir(exist_ok=True)
            (runtime / "finance.config.json").write_text(
                json.dumps({"RUNTIME_ENVIRONMENT": "private"})
            )

            with self.assertRaisesRegex(RuntimeError, "non-synthetic runtime"):
                load_synthetic_expenses(runtime)


if __name__ == "__main__":
    unittest.main()
