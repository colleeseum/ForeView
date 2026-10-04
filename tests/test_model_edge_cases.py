# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

from tests.support import (
    account_category_totals,
    account_summary,
    add_balance_snapshot,
    add_real_estate_projection,
    create_account,
    create_person,
    create_real_estate_asset,
    ensure_domain_schema,
    import_csv_transactions,
    import_rbc_statement_pdf,
    migrate_legacy_fixed_deposits,
    parse_rbc_statement_summary,
    real_estate_summary,
    recalculate_transaction_balances,
    reconcile_account_balance,
    repair_imported_csv_dates,
    repair_imported_pdf_descriptions,
    resolve_import_account,
    set_account_current_interest_rate,
    set_account_owners,
    set_real_estate_owners,
    transaction_opening_balances,
    update_account,
    update_real_estate_asset,
)


class ModelEdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.connection_context = closing(sqlite3.connect(":memory:"))
        self.connection = self.connection_context.__enter__()
        self.connection.row_factory = sqlite3.Row
        ensure_domain_schema(self.connection)

    def tearDown(self):
        self.connection_context.__exit__(None, None, None)

    def test_legacy_fixed_deposit_migration_copies_parent_and_owners_once(self):
        person = create_person(self.connection, "Synthetic Owner")
        parent = create_account(
            self.connection,
            "Synthetic TFSA",
            "tfsa",
            account_number="SYN-TFSA",
            institution="Synthetic Bank",
        )
        set_account_owners(self.connection, parent, [(person, 1.0)])
        self.connection.execute(
            """INSERT INTO fixed_term_deposits(
                   account_id, name, principal, interest_rate, start_date,
                   maturity_date, maturity_value
               ) VALUES (?, 'GIC #12345', 10000, 0.04, '2026-01-01',
                         '2027-01-01', 10400)""",
            (parent,),
        )

        self.assertEqual(migrate_legacy_fixed_deposits(self.connection), 1)
        self.assertEqual(migrate_legacy_fixed_deposits(self.connection), 0)
        child = self.connection.execute(
            """SELECT id, parent_account_id, current_interest_rate, maturity_value
               FROM accounts WHERE asset_kind = 'gic'"""
        ).fetchone()
        self.assertEqual(tuple(child[1:]), (parent, 0.04, 10400.0))
        owner = self.connection.execute(
            "SELECT person_id, ownership_share FROM account_owners WHERE account_id = ?",
            (child[0],),
        ).fetchone()
        self.assertEqual(tuple(owner), (person, 1.0))

    def test_account_and_balance_validation_rejects_invalid_financial_state(self):
        parent = create_account(self.connection, "Parent", "tfsa", account_number="PARENT")
        account = create_account(
            self.connection, "Savings", "non_registered", account_number="SAVINGS"
        )
        invalid_creates = (
            {"account_number": "A", "asset_kind": "security"},
            {"account_number": "", "asset_kind": "gic"},
        )
        for values in invalid_creates:
            with self.subTest(values=values), self.assertRaises(ValueError):
                create_account(self.connection, "Invalid", "tfsa", **values)

        invalid_updates = (
            {"account_number": "", "asset_kind": "account"},
            {"account_number": "A", "asset_kind": "security"},
            {"account_number": "", "asset_kind": "gic"},
        )
        for values in invalid_updates:
            with self.subTest(values=values), self.assertRaises(ValueError):
                update_account(
                    self.connection,
                    account,
                    name="Invalid",
                    institution=None,
                    **values,
                )

        update_account(
            self.connection,
            account,
            name="Savings renamed",
            account_number="SAVINGS-2",
            institution="Synthetic Bank",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT name FROM accounts WHERE id = ?", (account,)
            ).fetchone()[0],
            "Savings renamed",
        )
        for operation in (
            lambda: set_account_current_interest_rate(self.connection, account, -0.01),
            lambda: add_balance_snapshot(self.connection, account, "2026-01-01", -1),
            lambda: add_balance_snapshot(
                self.connection, account, "2026-01-01", 1, interest_rate=-0.01
            ),
        ):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()

        gic = create_account(
            self.connection,
            "Valid GIC",
            "tfsa",
            account_number="",
            asset_kind="gic",
            parent_account_id=parent,
        )
        self.assertGreater(gic, 0)

    def test_real_estate_constraints_and_summary_calculations(self):
        invalid_assets = (
            {"name": "", "estimated_value": 1, "valuation_date": "2026-01-01"},
            {"name": "Land", "estimated_value": -1, "valuation_date": "2026-01-01"},
            {
                "name": "Land",
                "estimated_value": 1,
                "valuation_date": "2026-01-01",
                "ownership_share": 0,
            },
            {
                "name": "Land",
                "estimated_value": 1,
                "valuation_date": "2026-01-01",
                "effective_tax_rate": 1.1,
            },
            {"name": "Land", "estimated_value": 1, "valuation_date": "not-a-date"},
        )
        for values in invalid_assets:
            with self.subTest(values=values), self.assertRaises(ValueError):
                create_real_estate_asset(self.connection, **values)

        asset = create_real_estate_asset(
            self.connection,
            "Synthetic Land",
            150000,
            "2026-01-01",
            acb=100000,
            effective_tax_rate=0.25,
        )
        first = create_person(self.connection, "First Owner")
        second = create_person(self.connection, "Second Owner")
        for owners in ([], [(first, 0.4)], [(first, 1.1), (second, -0.1)]):
            with self.subTest(owners=owners), self.assertRaises(ValueError):
                set_real_estate_owners(self.connection, asset, owners)
        set_real_estate_owners(self.connection, asset, [(first, 0.5), (second, 0.5)])

        projection = add_real_estate_projection(
            self.connection,
            asset,
            "2030-01-01",
            175000,
            projected_acb=100000,
            effective_tax_rate=0.3,
            note="Synthetic projection",
        )
        self.assertGreater(projection, 0)
        for values in (
            {"projection_date": "2030-01-01", "projected_value": -1},
            {
                "projection_date": "2030-01-01",
                "projected_value": 1,
                "effective_tax_rate": -0.1,
            },
            {"projection_date": "invalid", "projected_value": 1},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                add_real_estate_projection(self.connection, asset, **values)

        summary = real_estate_summary(self.connection)[0]
        self.assertEqual(summary["estimated_gain"], 50000.0)
        self.assertEqual(summary["estimated_tax"], 12500.0)
        self.assertEqual(summary["estimated_net_value"], 137500.0)
        self.assertEqual(len(summary["owners"]), 2)
        self.assertEqual(len(summary["projections"]), 1)

        update_real_estate_asset(
            self.connection,
            asset,
            "Synthetic Home",
            160000,
            "2026-02-01",
            principal_residence=True,
        )
        home = real_estate_summary(self.connection)[0]
        self.assertEqual(home["estimated_tax"], 0.0)
        self.assertEqual(home["estimated_net_value"], 160000.0)
        with self.assertRaisesRegex(ValueError, "not found"):
            update_real_estate_asset(self.connection, 9999, "Missing", 1, "2026-01-01")

    def test_csv_import_rejects_malformed_and_cross_account_data(self):
        account = create_account(
            self.connection,
            "RBC Synthetic",
            "non_registered",
            account_number="123-456",
            institution="RBC",
        )
        self.connection.commit()
        cases = (
            (9999, b"Date,Amount\n2026-01-01,1\n", "Account not found"),
            (account, b"", "no header"),
            (account, b"Wrong,Columns\n1,2\n", "Unrecognized CSV"),
            (account, b"Date,Amount\n2026-01-01,not-money\n", "Invalid amount"),
            (
                account,
                "Type de compte,Numéro du compte,Date de l'opération,Description 1,CAD$\n"
                "Compte,999,1/1/2026,Deposit,1\n".encode(),
                "different account number",
            ),
        )
        for account_id, content, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                import_csv_transactions(self.connection, account_id, "synthetic.csv", content)

    def test_repair_helpers_normalize_legacy_dates_and_descriptions(self):
        account = create_account(self.connection, "Legacy", "tfsa", account_number="LEGACY")
        batch = self.connection.execute(
            "INSERT INTO import_batches(account_id, filename, file_hash) VALUES (?, 'old.pdf', 'old')",
            (account,),
        ).lastrowid
        raw_eq = self.connection.execute(
            "INSERT INTO raw_transactions(batch_id, row_number, row_hash, raw_data) VALUES (?, 1, 'eq', ?)",
            (
                batch,
                json.dumps(
                    {
                        "source": "eq_pdf",
                        "raw_line": "Jan 12 Synthetic deposit $10.00 $110.00",
                    }
                ),
            ),
        ).lastrowid
        raw_rbc = self.connection.execute(
            "INSERT INTO raw_transactions(batch_id, row_number, row_hash, raw_data) VALUES (?, 2, 'rbc', ?)",
            (batch, json.dumps({"source": "rbc_tfsa_pdf"})),
        ).lastrowid
        self.connection.executemany(
            """INSERT INTO transactions(
                   account_id, raw_transaction_id, transaction_date, amount, description
               ) VALUES (?, ?, ?, ?, ?)""",
            [
                (account, raw_eq, "31Oct2025", 10, ""),
                (account, raw_rbc, "2025-11-01", 2, "Intérêtsréinvesti"),
            ],
        )
        self.connection.commit()

        self.assertEqual(repair_imported_csv_dates(self.connection), 1)
        self.assertEqual(repair_imported_pdf_descriptions(self.connection), 2)
        rows = self.connection.execute(
            "SELECT transaction_date, description, category FROM transactions ORDER BY id"
        ).fetchall()
        self.assertEqual(tuple(rows[0]), ("2025-10-31", "Synthetic deposit", None))
        self.assertEqual(tuple(rows[1]), ("2025-11-01", "Interest reinvested", "Interest"))
        self.assertEqual(recalculate_transaction_balances(self.connection, account), 0)

    def test_rbc_statement_summary_parses_english_and_french_documents(self):
        documents = (
            (
                """Personal Deposit Account
Account Summary
For August 14, 2026 - September 14, 2026
Transit Number: 99999 Account Number: 7777777
Opening Balance $9,541.20
Total deposits Total withdrawals + $48,000.00 - $49,335.51
Closing Balance $8,205.69
""",
                {
                    "account_number": "99999-7777777",
                    "statement_start": "2026-08-14",
                    "statement_end": "2026-09-14",
                    "opening_balance": 9541.20,
                    "closing_balance": 8205.69,
                    "statement_deposits": 48000.0,
                    "statement_withdrawals": 49335.51,
                },
            ),
            (
                """Compte de dépôt de particulier | 14 août 2026 - 14 septembre 2026
Sommaire du compte
Numéro de transit : 99999 Numéro de compte : 7777777
Solde d’ouverture 9 541,20 $
Solde de clôture 8 205,69 $
""",
                {
                    "account_number": "99999-7777777",
                    "statement_start": "2026-08-14",
                    "statement_end": "2026-09-14",
                    "opening_balance": 9541.20,
                    "closing_balance": 8205.69,
                    "statement_deposits": None,
                    "statement_withdrawals": None,
                },
            ),
        )

        class Page:
            def __init__(self, text):
                self.text = text

            def extract_text(self):
                return self.text

        class Pdf:
            def __init__(self, text):
                self.pages = [Page(text)]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        for text, expected in documents:
            with self.subTest(language=expected["statement_deposits"] is None):
                with patch("tests.support.pdfplumber.open", return_value=Pdf(text)):
                    self.assertEqual(parse_rbc_statement_summary(b"synthetic"), expected)
        with patch("tests.support.pdfplumber.open", return_value=Pdf("not a statement")):
            with self.assertRaisesRegex(ValueError, "does not look like"):
                parse_rbc_statement_summary(b"synthetic")
        incomplete = (
            "Personal Deposit Account Account Summary For August 14, 2026 - September 14, 2026"
        )
        with patch("tests.support.pdfplumber.open", return_value=Pdf(incomplete)):
            with self.assertRaisesRegex(ValueError, "Could not read"):
                parse_rbc_statement_summary(b"synthetic")

    def test_auto_detected_import_accounts_are_created_once_for_each_institution(self):
        class Pdf:
            pages = []

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        cases = (
            (
                "import_rbc_gic_transaction_history_pdf",
                "institutions.rbc.document_importers.parse_rbc_gic_transaction_history",
                {"account_number": "RBC-GIC"},
                "tfsa",
                "RBC",
            ),
            (
                "import_rbc_tfsa_pdf",
                "institutions.rbc.document_importers.parse_rbc_tfsa_statement",
                {"account_number": "RBC-TFSA"},
                "tfsa",
                "RBC",
            ),
            (
                "import_rbc_statement_pdf",
                "institutions.rbc.document_importers.parse_rbc_statement_summary",
                {"account_number": "RBC-CASH"},
                "non_registered",
                "RBC",
            ),
            (
                "import_manulife_rrsp_pdf",
                "institutions.manulife.document_importers.parse_rrsp_statement",
                {"account_number": "MANULIFE-RRSP"},
                "rrsp",
                "Manulife",
            ),
            (
                "import_sunlife_transaction_history_pdf",
                "institutions.sunlife.document_importers.parse_sunlife_transaction_history",
                {"account_number": "SUNLIFE-HISTORY"},
                "rrsp",
                "Sun Life",
            ),
            (
                "import_sunlife_rrsp_pdf",
                "institutions.sunlife.document_importers.parse_sunlife_rrsp_statement",
                {"account_number": "SUNLIFE-RRSP"},
                "rrsp",
                "Sun Life",
            ),
        )
        with patch("tests.support.pdfplumber.open", return_value=Pdf()):
            for importer, parser, parsed, category, institution in cases:
                with self.subTest(importer=importer), patch(parser, return_value=parsed):
                    account_id = resolve_import_account(
                        self.connection, importer, b"synthetic", "synthetic.pdf"
                    )
                    repeated_id = resolve_import_account(
                        self.connection, importer, b"synthetic", "synthetic.pdf"
                    )
                    self.assertEqual(repeated_id, account_id)
                    row = self.connection.execute(
                        "SELECT account_type, institution FROM accounts WHERE id = ?",
                        (account_id,),
                    ).fetchone()
                    self.assertEqual(tuple(row), (category, institution))
            with self.assertRaisesRegex(ValueError, "Cannot auto-detect"):
                resolve_import_account(
                    self.connection, "unknown_importer", b"synthetic", "unknown.pdf"
                )

    def test_rbc_reconciliation_reimport_restores_snapshot_without_duplication(self):
        account = create_account(
            self.connection,
            "RBC Synthetic",
            "non_registered",
            account_number="99999-7777777",
            institution="RBC",
        )
        import_csv_transactions(
            self.connection,
            account,
            "activity.csv",
            b"Date,Amount,Description\n2026-08-20,25,Deposit\n",
        )
        summary = {
            "account_number": "99999-7777777",
            "statement_start": "2026-08-14",
            "statement_end": "2026-09-14",
            "opening_balance": 100.0,
            "closing_balance": 125.0,
            "statement_deposits": 25.0,
            "statement_withdrawals": 0.0,
        }
        with patch(
            "institutions.rbc.document_importers.parse_rbc_statement_summary", return_value=summary
        ):
            first = import_rbc_statement_pdf(
                self.connection, account, "statement.pdf", b"same-statement"
            )
            self.connection.execute(
                "DELETE FROM balance_snapshots WHERE account_id = ?", (account,)
            )
            self.connection.commit()
            second = import_rbc_statement_pdf(
                self.connection, account, "statement-copy.pdf", b"same-statement"
            )
        self.assertEqual(first["reconciliation_status"], "reconciled")
        self.assertEqual(second["status"], "already_reconciled")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM statement_reconciliations WHERE account_id = ?",
                (account,),
            ).fetchone()[0],
            1,
        )
        snapshot = self.connection.execute(
            "SELECT snapshot_date, amount FROM balance_snapshots WHERE account_id = ?",
            (account,),
        ).fetchone()
        self.assertEqual(tuple(snapshot), ("2026-09-14", 125.0))

    def test_opening_balances_explain_partial_history_and_manual_reconciliation(self):
        explicit = create_account(
            self.connection, "Explicit", "non_registered", account_number="EXPLICIT"
        )
        calculated = create_account(
            self.connection, "Calculated", "non_registered", account_number="CALCULATED"
        )
        new_account = create_account(
            self.connection, "New account", "non_registered", account_number="NEW"
        )
        add_balance_snapshot(self.connection, new_account, "2026-09-04", 1234.56)
        import_csv_transactions(
            self.connection,
            explicit,
            "explicit.csv",
            b"Date,Amount,Description,Balance\n"
            b"2026-08-30,100,Transfer,24447.50\n"
            b"2026-08-31,52.50,Interest,24500\n",
        )
        add_balance_snapshot(self.connection, calculated, "2026-09-03", 5000)
        import_csv_transactions(
            self.connection,
            calculated,
            "calculated.csv",
            b"Date,Amount,Description\n"
            b"2026-09-01,100,Deposit\n"
            b"2026-09-02,-25,Purchase\n"
            b"2026-09-03,50,Refund\n",
        )
        recalculate_transaction_balances(self.connection, calculated)

        openings = {
            row["account_id"]: row
            for row in transaction_opening_balances(self.connection, account_type="non_registered")
        }
        self.assertEqual(openings[explicit]["balance_after"], 24347.50)
        self.assertEqual(openings[calculated]["balance_after"], 4875.0)
        self.assertEqual(openings[new_account]["balance_after"], 1234.56)
        self.assertEqual(openings[explicit]["description"], "Opening balance")

        result = reconcile_account_balance(self.connection, calculated, "2026-09-03", 6000)
        self.assertEqual(result["previous_balance"], 5000.0)
        self.assertEqual(result["difference"], 1000.0)
        self.assertEqual(result["status"], "adjusted")
        calculated_balances = [
            row[0]
            for row in self.connection.execute(
                "SELECT balance_after FROM transactions WHERE account_id = ? ORDER BY transaction_date",
                (calculated,),
            )
        ]
        self.assertEqual(calculated_balances, [5975.0, 5950.0, 6000.0])

        reconcile_account_balance(self.connection, explicit, "2026-09-01", 25000)
        explicit_balances = [
            row[0]
            for row in self.connection.execute(
                "SELECT balance_after FROM transactions WHERE account_id = ? ORDER BY transaction_date",
                (explicit,),
            )
        ]
        self.assertEqual(explicit_balances, [24447.50, 24500.0])

    def test_reconciliation_rejects_invalid_account_date_and_amount(self):
        account = create_account(
            self.connection, "Synthetic", "non_registered", account_number="SYN"
        )
        cases = (
            (account, "invalid", 1, "Invalid reconciliation date"),
            (account, "2026-01-01", -1, "cannot be negative"),
            (9999, "2026-01-01", 1, "Account not found"),
        )
        for account_id, value_date, amount, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                reconcile_account_balance(self.connection, account_id, value_date, amount)

    def test_gic_principal_is_the_balance_fallback_when_no_snapshot_exists(self):
        parent = create_account(self.connection, "TFSA", "tfsa", account_number="TFSA-PRINCIPAL")
        gic = create_account(
            self.connection,
            "Maturity notice GIC",
            "tfsa",
            account_number="",
            asset_kind="gic",
            parent_account_id=parent,
            start_date="2025-09-28",
            maturity_date="2026-09-28",
            principal=5000,
            maturity_value=5200,
        )
        summary = {item["id"]: item for item in account_summary(self.connection)}
        self.assertEqual(summary[gic]["latest_amount"], 5000)
        self.assertEqual(summary[gic]["latest_date"], "2025-09-28")

        cash_parent = create_account(
            self.connection, "Cash and GIC TFSA", "tfsa", account_number="TFSA-CASH-GIC"
        )
        cash_gic = create_account(
            self.connection,
            "Cash parent GIC",
            "tfsa",
            account_number="",
            asset_kind="gic",
            parent_account_id=cash_parent,
            principal=10450,
        )
        add_balance_snapshot(self.connection, cash_parent, "2026-01-01", 107.5)

        consolidated = create_account(
            self.connection, "Consolidated TFSA", "tfsa", account_number="TFSA-CONSOLIDATED"
        )
        included_gic = create_account(
            self.connection,
            "Included GIC",
            "tfsa",
            account_number="",
            asset_kind="gic",
            parent_account_id=consolidated,
            principal=10000,
        )
        add_balance_snapshot(self.connection, consolidated, "2026-01-01", 50000)
        add_balance_snapshot(self.connection, included_gic, "2026-01-01", 10250)
        self.connection.execute(
            "UPDATE accounts SET balance_includes_children = 1 WHERE id = ?",
            (consolidated,),
        )
        self.connection.commit()
        accounts = account_summary(self.connection)
        by_id = {item["id"]: item for item in accounts}
        self.assertEqual(by_id[parent]["rollup_amount"], 5000)
        self.assertEqual(by_id[parent]["non_gic_amount"], 0)
        self.assertEqual(by_id[gic]["rollup_amount"], 5000)
        self.assertEqual(by_id[cash_parent]["rollup_amount"], 10557.5)
        self.assertEqual(by_id[cash_parent]["non_gic_amount"], 107.5)
        self.assertEqual(by_id[cash_gic]["rollup_amount"], 10450)
        self.assertEqual(by_id[consolidated]["rollup_amount"], 50000)
        self.assertEqual(by_id[consolidated]["non_gic_amount"], 39750)
        self.assertEqual(by_id[included_gic]["rollup_amount"], 10250)
        tfsa = next(item for item in account_category_totals(accounts) if item["type"] == "tfsa")
        self.assertEqual(tfsa["total"], 65557.5)
        self.assertEqual(tfsa["count"], 3)
        self.assertEqual(tfsa["gic_count"], 3)


if __name__ == "__main__":
    unittest.main()
