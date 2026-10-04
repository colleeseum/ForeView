"""Re-importing data the application already holds must not duplicate transactions."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from infrastructure.runtime_config import RuntimeConfig
from institution_support.document_detection import detect_importer
from institutions.questrade.sync import sync_questrade_connection
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from synthetic_documents import create_synthetic_fixture_set
from tests.support import (
    create_account,
    create_person,
    ensure_domain_schema,
    import_csv_transactions,
    import_pdf_transactions,
    resolve_import_account,
    set_account_owners,
)

# Appending a PDF comment changes the file hash without changing its content,
# as happens when a statement is downloaded again.
REDOWNLOADED = b"\n% downloaded again\n"


def _count(connection: sqlite3.Connection) -> int:
    return connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]


class DocumentReimportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.fixtures = create_synthetic_fixture_set(Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        ensure_domain_schema(self.connection)
        self.addCleanup(self.connection.close)

    def _account_and_importer(self, key: str, content: bytes):
        if key == "eq_pdf":
            account = create_account(
                self.connection,
                "EQ",
                "non_registered",
                account_number="999-888-777",
                institution="EQ Bank",
            )
            return account, import_pdf_transactions
        detected = detect_importer(content)
        self.assertIsNotNone(detected)
        if key == "achieva_gic_pdf":
            owner = create_person(self.connection, "Owner")
            account = create_account(
                self.connection,
                "Achieva",
                "tfsa",
                account_number="SYN-ACH-001",
                institution="Achieva",
            )
            set_account_owners(self.connection, account, [(owner, 1.0)])
            return account, detected.importer
        account = resolve_import_account(
            self.connection, detected.spec.importer_name, content, "statement.pdf"
        )
        return account, detected.importer

    def test_redownloaded_statement_adds_no_transactions(self):
        for key in (
            "eq_pdf",
            "achieva_gic_pdf",
            "rbc_gic_pdf",
            "rbc_resp_pdf",
            "rbc_tfsa_pdf",
            "manulife_pdf",
            "sunlife_history_pdf",
        ):
            with self.subTest(key):
                self.setUp()
                content = self.fixtures[key].read_bytes()
                account, importer = self._account_and_importer(key, content)
                importer(self.connection, account, "first.pdf", content)
                imported = _count(self.connection)
                self.assertGreater(imported, 0)

                importer(self.connection, account, "again.pdf", content + REDOWNLOADED)

                self.assertEqual(_count(self.connection), imported)


class CsvReimportTests(unittest.TestCase):
    HEADER = "Date,Description,Amount\n"

    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        ensure_domain_schema(self.connection)
        self.addCleanup(self.connection.close)
        self.account = create_account(
            self.connection, "CSV", "non_registered", account_number="CSV-1", institution="Test"
        )

    def _import(self, name: str, rows: str, newline: str = "\n"):
        content = (self.HEADER + rows).replace("\n", newline).encode()
        return import_csv_transactions(self.connection, self.account, name, content)

    def test_reexport_with_different_bytes_adds_nothing(self):
        rows = "2026-01-10,Pay,100\n2026-02-10,Pay,100\n2026-03-10,Pay,100\n"
        self._import("jan-mar.csv", rows)

        result = self._import("jan-mar-windows.csv", rows, newline="\r\n")

        self.assertEqual(_count(self.connection), 3)
        self.assertEqual((result["imported"], result["duplicates"]), (0, 3))

    def test_overlapping_period_imports_only_new_rows(self):
        self._import("jan-mar.csv", "2026-01-10,Pay,100\n2026-02-10,Pay,100\n2026-03-10,Pay,100\n")

        result = self._import(
            "feb-apr.csv", "2026-02-10,Pay,100\n2026-03-10,Pay,100\n2026-04-10,Pay,100\n"
        )

        self.assertEqual(_count(self.connection), 4)
        self.assertEqual((result["imported"], result["duplicates"]), (1, 2))

    def test_identical_transactions_on_one_day_are_kept_and_not_reimported(self):
        repeated = "2026-01-10,Coffee,-5\n2026-01-10,Coffee,-5\n"
        first = self._import("january.csv", repeated)
        self.assertEqual(first["imported"], 2)

        self._import("january-again.csv", "2026-01-09,Pay,100\n" + repeated)

        self.assertEqual(_count(self.connection), 3)

    def test_a_third_repeat_in_a_later_export_is_imported(self):
        self._import("first.csv", "2026-01-10,Coffee,-5\n")

        self._import("second.csv", "2026-01-10,Coffee,-5\n2026-01-10,Coffee,-5\n")

        self.assertEqual(_count(self.connection), 2)

    def test_printed_balance_separates_identical_purchases_across_partial_days(self):
        header = "Date,Description,Amount,Balance\n"
        morning = header + "2026-01-09,Pay,100,100\n2026-01-10,Coffee,-5,95\n"
        afternoon = header + "2026-01-10,Coffee,-5,90\n2026-01-11,Pay,100,190\n"
        import_csv_transactions(self.connection, self.account, "morning.csv", morning.encode())

        result = import_csv_transactions(
            self.connection, self.account, "afternoon.csv", afternoon.encode()
        )

        self.assertEqual((result["imported"], result["duplicates"]), (2, 0))
        self.assertEqual(_count(self.connection), 4)

    def test_printed_balance_still_matches_a_true_overlap(self):
        header = "Date,Description,Amount,Balance\n"
        rows = "2026-01-10,Coffee,-5,95\n2026-01-10,Coffee,-5,90\n"
        import_csv_transactions(self.connection, self.account, "a.csv", (header + rows).encode())

        result = import_csv_transactions(
            self.connection,
            self.account,
            "b.csv",
            (header + rows + "2026-01-11,Pay,100,190\n").encode(),
        )

        self.assertEqual((result["imported"], result["duplicates"]), (1, 2))

    def test_same_row_in_another_account_is_not_a_duplicate(self):
        other = create_account(
            self.connection, "Other", "non_registered", account_number="CSV-2", institution="Test"
        )
        self._import("mine.csv", "2026-01-10,Pay,100\n")

        theirs = self.HEADER + "2026-01-10,Pay,100\n2026-01-11,Other,1\n"
        import_csv_transactions(self.connection, other, "theirs.csv", theirs.encode())

        self.assertEqual(_count(self.connection), 3)


class QuestradeReimportTests(unittest.TestCase):
    ACCOUNT = {"number": "SYN-QT-1", "type": "TFSA"}
    ACTIVITY = {
        "transactionDate": "2026-09-01T12:00:00Z",
        "netAmount": 25.0,
        "type": "Dividend",
        "symbol": "SYN",
        "description": "Synthetic dividend",
    }

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.runtime = RuntimeConfig(Path(directory.name))
        with self.runtime.connect() as connection:
            ensure_domain_schema(connection)

    def _api(self, _authorization, path: str):
        if path == "/v1/accounts":
            return {"accounts": [self.ACCOUNT]}
        if "/activities?" in path and path not in self.served:
            self.served.add(path)
            activities = getattr(self, "activities", [self.ACTIVITY])
            return {"activities": activities} if not self.activity_sent else {"activities": []}
        return {}

    def _sync(self, login: str):
        self.served: set[str] = set()
        self.activity_sent = False

        def api(authorization, path):
            response = self._api(authorization, path)
            if response.get("activities"):
                self.activity_sent = True
            return response

        with self.runtime.connect() as connection:
            QuestradeAuthorizationRepository(connection).add_if_absent(
                login,
                access_token="unused",
                refresh_token="unused",
                api_server="https://api01.iq.questrade.com/",
            )
        return sync_questrade_connection(
            self.runtime.connect,
            login,
            api_getter=api,
            refresh_expiring=lambda _connection: None,
            refresh_authorization=lambda _connection, _authorization: None,
        )

    def _transactions(self) -> int:
        with self.runtime.connect() as connection:
            return _count(connection)

    def test_same_login_resync_is_idempotent(self):
        self._sync("alex")
        self._sync("alex")

        self.assertEqual(self._transactions(), 1)

    def test_same_day_activities_with_different_timestamps_are_both_kept(self):
        later = {**self.ACTIVITY, "transactionDate": "2026-09-01T15:30:00Z"}
        self.activities = [self.ACTIVITY, later]

        self._sync("alex")
        self._sync("alex")

        self.assertEqual(self._transactions(), 2)

    def test_renamed_login_does_not_duplicate_account_activity(self):
        self._sync("alex")

        self._sync("alex-renamed")

        self.assertEqual(self._transactions(), 1)


if __name__ == "__main__":
    unittest.main()
