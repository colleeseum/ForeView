# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import sqlite3
import tempfile
import unittest
from pathlib import Path

from institution_support.document_detection import detect_importer
from synthetic_documents import SYNTHETIC_NOTICE, create_synthetic_fixture_set
from tests.support import (
    add_balance_snapshot,
    create_account,
    create_person,
    ensure_domain_schema,
    import_achieva_gic_pdf,
    import_csv_transactions,
    import_pdf_transactions,
    recalculate_transaction_balances,
    resolve_import_account,
    set_account_owners,
)


class SyntheticDocumentIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.fixtures = create_synthetic_fixture_set(Path(cls.temporary_directory.name))

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        ensure_domain_schema(self.connection)

    def tearDown(self):
        self.connection.close()

    def _auto_import(self, key):
        path = self.fixtures[key]
        content = path.read_bytes()
        detected = detect_importer(content)
        self.assertIsNotNone(detected)
        account_id = resolve_import_account(
            self.connection,
            detected.spec.importer_name,
            content,
            path.name,
        )
        result = detected.importer(self.connection, account_id, path.name, content)
        return detected, account_id, result

    def test_fixture_matrix_contains_eleven_pdfs_and_three_csvs(self):
        suffixes = [path.suffix for path in self.fixtures.values()]
        self.assertEqual(suffixes.count(".pdf"), 11)
        self.assertEqual(suffixes.count(".csv"), 3)

    def test_every_pdf_is_visibly_marked_synthetic(self):
        import pdfplumber

        for path in self.fixtures.values():
            if path.suffix != ".pdf":
                continue
            with self.subTest(path=path.name), pdfplumber.open(path) as pdf:
                self.assertIn(SYNTHETIC_NOTICE, pdf.pages[0].extract_text())

    def test_achieva_pdf_detects_and_imports_gic_child(self):
        person = create_person(self.connection, "Synthetic Owner")
        parent = create_account(
            self.connection,
            "Synthetic Achieva TFSA",
            "tfsa",
            account_number="SYN-ACH-001",
            institution="Achieva",
        )
        set_account_owners(self.connection, parent, [(person, 1.0)])
        path = self.fixtures["achieva_gic_pdf"]
        detected = detect_importer(path.read_bytes())
        self.assertEqual(detected.spec.name, "Achieva GIC PDF")
        result = import_achieva_gic_pdf(self.connection, parent, path.name, path.read_bytes())
        self.assertEqual(result["imported"], 2)
        child = self.connection.execute(
            "SELECT id FROM accounts WHERE parent_account_id = ? AND asset_kind = 'gic'",
            (parent,),
        ).fetchone()
        self.assertIsNotNone(child)
        self.assertEqual(
            self.connection.execute(
                "SELECT amount FROM balance_snapshots WHERE account_id = ?",
                (child[0],),
            ).fetchone()[0],
            10450,
        )

    def test_eq_pdf_imports_real_extracted_rows_and_balances(self):
        path = self.fixtures["eq_pdf"]
        self.assertIsNone(detect_importer(path.read_bytes()))
        account = create_account(
            self.connection,
            "Synthetic EQ",
            "non_registered",
            account_number="999-888-777",
            institution="EQ",
        )
        result = import_pdf_transactions(self.connection, account, path.name, path.read_bytes())
        self.assertEqual(result["imported"], 3)
        rows = self.connection.execute(
            "SELECT amount, balance_after FROM transactions ORDER BY transaction_date"
        ).fetchall()
        self.assertEqual([tuple(row) for row in rows], [(100, 1100), (-25, 1075), (2.5, 1077.5)])

    def test_rbc_gic_history_auto_creates_parent_and_child(self):
        detected, parent, result = self._auto_import("rbc_gic_pdf")
        self.assertEqual(detected.spec.name, "RBC GIC transaction history")
        self.assertEqual(result["imported"], 3)
        child = self.connection.execute(
            "SELECT id FROM accounts WHERE parent_account_id = ? AND asset_kind = 'gic'",
            (parent,),
        ).fetchone()
        self.assertIsNotNone(child)
        snapshots = dict(
            self.connection.execute(
                "SELECT account_id, amount FROM balance_snapshots WHERE account_id IN (?, ?)",
                (parent, child[0]),
            ).fetchall()
        )
        self.assertEqual(snapshots[parent], 107.5)
        self.assertEqual(snapshots[child[0]], 10450)

    def test_rbc_resp_history_auto_creates_resp_parent_and_gic_child(self):
        detected, parent, result = self._auto_import("rbc_resp_pdf")
        self.assertEqual(detected.spec.name, "RBC RESP GIC transaction history")
        self.assertEqual(result["imported"], 3)
        self.assertEqual(
            self.connection.execute(
                "SELECT account_number FROM accounts WHERE id = ?", (parent,)
            ).fetchone()[0],
            "999888777",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT account_type FROM accounts WHERE id = ?", (parent,)
            ).fetchone()[0],
            "resp",
        )
        child = self.connection.execute(
            "SELECT id FROM accounts WHERE parent_account_id = ? AND asset_kind = 'gic'",
            (parent,),
        ).fetchone()
        self.assertIsNotNone(child)

    def test_rbc_tfsa_statement_auto_creates_account_and_gic(self):
        detected, account, result = self._auto_import("rbc_tfsa_pdf")
        self.assertEqual(detected.spec.name, "RBC TFSA statement")
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["gics"], 1)
        self.assertEqual(
            self.connection.execute(
                "SELECT amount FROM balance_snapshots WHERE account_id = ?",
                (account,),
            ).fetchone()[0],
            107.5,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM fixed_term_deposits WHERE account_id = ?",
                (account,),
            ).fetchone()[0],
            1,
        )

    def test_rbc_maturity_notice_updates_same_auto_created_account(self):
        _, account, first = self._auto_import("rbc_tfsa_pdf")
        path = self.fixtures["rbc_maturity_pdf"]
        detected = detect_importer(path.read_bytes())
        resolved = resolve_import_account(
            self.connection,
            detected.spec.importer_name,
            path.read_bytes(),
            path.name,
        )
        second = detected.importer(self.connection, resolved, path.name, path.read_bytes())
        self.assertEqual(account, resolved)
        self.assertEqual(first["document_type"], "statement")
        self.assertEqual(second["document_type"], "maturity_notice")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM fixed_term_deposits WHERE account_id = ?",
                (account,),
            ).fetchone()[0],
            2,
        )

    def test_rbc_deposit_pdf_reconciles_matching_rbc_csv(self):
        pdf = self.fixtures["rbc_deposit_pdf"]
        detected = detect_importer(pdf.read_bytes())
        account = resolve_import_account(
            self.connection,
            detected.spec.importer_name,
            pdf.read_bytes(),
            pdf.name,
        )
        csv_path = self.fixtures["rbc_csv"]
        imported = import_csv_transactions(
            self.connection,
            account,
            csv_path.name,
            csv_path.read_bytes(),
        )
        result = detected.importer(self.connection, account, pdf.name, pdf.read_bytes())
        self.assertEqual(imported["imported"], 2)
        self.assertEqual(result["reconciliation_status"], "reconciled")
        self.assertEqual(result["difference"], 0)

    def test_manulife_pdf_imports_transactions_balances_and_holding(self):
        detected, account, result = self._auto_import("manulife_pdf")
        self.assertEqual(detected.spec.name, "Manulife RRSP statement")
        self.assertEqual(result["imported"], 4)
        self.assertEqual(result["closing_value"], 60000)
        holding = self.connection.execute(
            "SELECT fund_code, market_value FROM investment_holdings WHERE account_id = ?",
            (account,),
        ).fetchone()
        self.assertEqual(tuple(holding), ("1234", 60000))

    def test_sunlife_statement_imports_snapshot_and_three_holdings(self):
        detected, account, result = self._auto_import("sunlife_pdf")
        self.assertEqual(detected.spec.name, "Sun Life RRSP statement")
        self.assertEqual(result["holdings"], 3)
        self.assertEqual(
            self.connection.execute(
                "SELECT SUM(market_value) FROM investment_holdings WHERE account_id = ?",
                (account,),
            ).fetchone()[0],
            90000,
        )

    def test_sunlife_history_imports_transfer_into_same_account(self):
        _, account, _ = self._auto_import("sunlife_pdf")
        path = self.fixtures["sunlife_history_pdf"]
        detected = detect_importer(path.read_bytes())
        resolved = resolve_import_account(
            self.connection,
            detected.spec.importer_name,
            path.read_bytes(),
            path.name,
        )
        result = detected.importer(self.connection, resolved, path.name, path.read_bytes())
        self.assertEqual(account, resolved)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(
            self.connection.execute(
                "SELECT amount FROM transactions WHERE account_id = ?",
                (account,),
            ).fetchone()[0],
            2500,
        )

    def test_duplicate_pdf_is_idempotent(self):
        path = self.fixtures["manulife_pdf"]
        content = path.read_bytes()
        detected = detect_importer(content)
        account = resolve_import_account(
            self.connection,
            detected.spec.importer_name,
            content,
            path.name,
        )
        first = detected.importer(self.connection, account, path.name, content)
        second = detected.importer(self.connection, account, path.name, content)
        self.assertEqual(first["imported"], 4)
        self.assertEqual(second["status"], "already_imported")
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 4
        )

    def test_generic_csv_preserves_supplied_running_balances(self):
        account = create_account(
            self.connection, "CSV balance", "non_registered", account_number="SYN-CSV-1"
        )
        path = self.fixtures["generic_balanced_csv"]
        result = import_csv_transactions(self.connection, account, path.name, path.read_bytes())
        self.assertEqual(result["imported"], 2)
        self.assertEqual(
            [
                row[0]
                for row in self.connection.execute(
                    "SELECT balance_after FROM transactions ORDER BY transaction_date"
                )
            ],
            [1100, 1075],
        )

    def test_generic_csv_without_balances_is_reconstructed_from_snapshot(self):
        account = create_account(
            self.connection, "CSV calculated", "non_registered", account_number="SYN-CSV-2"
        )
        path = self.fixtures["generic_calculated_csv"]
        import_csv_transactions(self.connection, account, path.name, path.read_bytes())
        add_balance_snapshot(self.connection, account, "2026-01-02", 1075)
        recalculate_transaction_balances(self.connection, account)
        self.assertEqual(
            [
                row[0]
                for row in self.connection.execute(
                    "SELECT balance_after FROM transactions ORDER BY transaction_date"
                )
            ],
            [1100, 1075],
        )

    def test_rbc_csv_profile_validates_account_and_combines_descriptions(self):
        account = create_account(
            self.connection,
            "Synthetic RBC",
            "non_registered",
            account_number="99999-8888888",
            institution="RBC",
        )
        path = self.fixtures["rbc_csv"]
        result = import_csv_transactions(self.connection, account, path.name, path.read_bytes())
        self.assertEqual(result["imported"], 2)
        descriptions = [
            row[0]
            for row in self.connection.execute(
                "SELECT description FROM transactions ORDER BY transaction_date"
            )
        ]
        self.assertEqual(descriptions, ["Synthetic deposit", "Synthetic purchase"])


if __name__ == "__main__":
    unittest.main()
