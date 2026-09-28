"""Reconciled periods are protected from silent changes by later imports."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from infrastructure.runtime_config import RuntimeConfig
from ingestion.reconciled_period_change import ReconciledPeriodChange
from institutions.questrade.sync import sync_questrade_connection
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from services.reconciliation_checkpoint_service import ReconciliationCheckpointService
from tests.support import (
    create_account,
    ensure_domain_schema,
    import_csv_transactions,
    reconcile_account_balance,
)

HEADER = "Date,Description,Amount,Balance\n"
JANUARY = HEADER + "2026-01-05,Pay,1000,1000\n2026-01-20,Rent,-400,600\n"


def _csv(*rows: str) -> bytes:
    return (HEADER + "".join(rows)).encode()


class ReconciliationCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        ensure_domain_schema(self.connection)
        self.addCleanup(self.connection.close)
        self.account = create_account(
            self.connection,
            "Chequing",
            "non_registered",
            account_number="CHQ-1",
            institution="Test",
        )
        import_csv_transactions(self.connection, self.account, "january.csv", JANUARY.encode())
        self.checkpoints = ReconciliationCheckpointService(self.connection)

    def _count(self, table: str = "transactions") -> int:
        return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608

    def _reconcile_january(self):
        return reconcile_account_balance(self.connection, self.account, "2026-01-31", 600.0)

    def test_matching_known_balance_creates_a_checkpoint(self):
        result = self._reconcile_january()

        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(result["reconciled_through"], "2026-01-31")
        [checkpoint] = self.checkpoints.active(self.account)
        self.assertEqual(
            (checkpoint.status, checkpoint.net_change, checkpoint.transaction_count),
            ("reconciled", 600.0, 2),
        )

    def test_mismatched_known_balance_creates_no_checkpoint(self):
        result = reconcile_account_balance(self.connection, self.account, "2026-01-31", 650.0)

        self.assertEqual(result["status"], "adjusted")
        self.assertIsNone(result["reconciled_through"])
        self.assertEqual(self.checkpoints.active(self.account), [])

    def test_import_into_reconciled_period_is_refused_and_rolled_back(self):
        self._reconcile_january()
        transactions, batches = self._count(), self._count("import_batches")

        with self.assertRaises(ReconciledPeriodChange) as refused:
            import_csv_transactions(
                self.connection,
                self.account,
                "late.csv",
                _csv("2026-01-25,Refund,50,650\n", "2026-02-02,Pay,1000,1650\n"),
            )

        self.assertEqual(refused.exception.reconciled_through, "2026-01-31")
        self.assertEqual(refused.exception.transaction_count, 1)
        self.assertEqual((self._count(), self._count("import_batches")), (transactions, batches))

    def test_duplicates_and_later_rows_pass_without_a_warning(self):
        self._reconcile_january()

        result = import_csv_transactions(
            self.connection,
            self.account,
            "january-and-february.csv",
            _csv(
                "2026-01-05,Pay,1000,1000\n",
                "2026-01-20,Rent,-400,600\n",
                "2026-02-02,Pay,1000,1600\n",
            ),
        )

        self.assertEqual((result["imported"], result["duplicates"]), (1, 2))
        self.assertEqual(self.checkpoints.active(self.account)[0].status, "reconciled")

    def test_confirmed_import_flags_the_period_until_reconciled_again(self):
        self._reconcile_january()

        import_csv_transactions(
            self.connection,
            self.account,
            "late.csv",
            _csv("2026-01-25,Refund,50,650\n"),
            allow_reconciled=True,
        )

        [flagged] = self.checkpoints.active(self.account)
        self.assertEqual((flagged.status, flagged.difference), ("needs_review", 50.0))

        reconcile_account_balance(self.connection, self.account, "2026-01-31", 650.0)

        [current] = self.checkpoints.active(self.account)
        self.assertEqual((current.status, current.net_change), ("reconciled", 650.0))

    def test_correcting_a_mistyped_reconciliation_replaces_it(self):
        account = create_account(
            self.connection, "Savings", "non_registered", account_number="SAV-9", institution="Test"
        )
        import_csv_transactions(
            self.connection,
            account,
            "no-balances.csv",
            b"Date,Description,Amount\n2026-01-05,Pay,1000\n2026-01-20,Rent,-400\n",
        )
        reconcile_account_balance(self.connection, account, "2026-01-31", 650.0)

        corrected = reconcile_account_balance(self.connection, account, "2026-01-31", 600.0)

        self.assertEqual(
            (corrected["status"], corrected["difference"], corrected["reconciled_through"]),
            ("reconciled", None, "2026-01-31"),
        )
        [checkpoint] = self.checkpoints.active(account)
        self.assertEqual((checkpoint.closing_balance, checkpoint.status), (600.0, "reconciled"))
        balances = [
            row[0]
            for row in self.connection.execute(
                "SELECT balance_after FROM transactions WHERE account_id = ?"
                " ORDER BY transaction_date",
                (account,),
            )
        ]
        self.assertEqual(balances, [1000.0, 600.0])

    def test_consecutive_periods_are_separate_checkpoints(self):
        self._reconcile_january()
        import_csv_transactions(
            self.connection, self.account, "february.csv", _csv("2026-02-02,Pay,1000,1600\n")
        )

        reconcile_account_balance(self.connection, self.account, "2026-02-28", 1600.0)

        periods = [
            (item.period_start, item.reconciled_through, item.transaction_count)
            for item in self.checkpoints.active(self.account)
        ]
        self.assertEqual(periods, [(None, "2026-01-31", 2), ("2026-02-01", "2026-02-28", 1)])

    def test_matched_rbc_statement_creates_a_statement_checkpoint(self):
        from unittest.mock import patch

        from tests.support import import_rbc_statement_pdf

        rbc = create_account(
            self.connection,
            "RBC",
            "non_registered",
            account_number="12345-6789012",
            institution="RBC",
        )
        import_csv_transactions(
            self.connection, rbc, "rbc.csv", _csv("2026-03-03,Pay,500,\n", "2026-03-20,Fee,-5,\n")
        )
        summary = {
            "account_number": "12345-6789012",
            "statement_start": "2026-03-01",
            "statement_end": "2026-03-31",
            "opening_balance": 100.0,
            "closing_balance": 595.0,
            "statement_deposits": 500.0,
            "statement_withdrawals": 5.0,
        }
        with patch(
            "institutions.rbc.document_importers.parse_rbc_statement_summary", return_value=summary
        ):
            result = import_rbc_statement_pdf(self.connection, rbc, "march.pdf", b"statement")

        self.assertEqual(result["reconciliation_status"], "reconciled")
        [checkpoint] = self.checkpoints.active(rbc)
        self.assertEqual(
            (checkpoint.source, checkpoint.period_start, checkpoint.reconciled_through),
            ("statement", "2026-03-01", "2026-03-31"),
        )


class QuestradeReconciledPeriodTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.runtime = RuntimeConfig(Path(directory.name))
        with self.runtime.connect() as connection:
            ensure_domain_schema(connection)
            QuestradeAuthorizationRepository(connection).add_if_absent(
                "alex",
                access_token="unused",
                refresh_token="unused",
                api_server="https://api01.iq.questrade.com/",
            )
        self.activities = []

    def _api(self, _authorization, path):
        if path == "/v1/accounts":
            return {"accounts": [{"number": "QT-1", "type": "TFSA"}]}
        if "/activities?" in path:
            activities, self.activities = self.activities, []
            return {"activities": activities}
        return {}

    def _sync(self):
        return sync_questrade_connection(
            self.runtime.connect,
            "alex",
            api_getter=self._api,
            refresh_expiring=lambda _connection: None,
            refresh_authorization=lambda _connection, _authorization: None,
            history_start="2026-01-01",
        )

    def test_backdated_activity_is_stored_and_the_period_flagged(self):
        self.activities = [
            {"transactionDate": "2026-01-10T12:00:00Z", "netAmount": 100.0, "type": "Deposit"}
        ]
        self._sync()
        with self.runtime.connect() as connection:
            account = connection.execute("SELECT id FROM accounts").fetchone()[0]
            ReconciliationCheckpointService(connection).record_known_balance(
                account, "2026-01-31", 100.0
            )
            connection.commit()

        self.activities = [
            {"transactionDate": "2026-01-15T12:00:00Z", "netAmount": 5.0, "type": "Dividend"}
        ]
        # The next sync starts after the first, so pretend Questrade posted it late.
        with self.runtime.connect() as connection:
            connection.execute("DELETE FROM activity_sync_state")
            connection.commit()
        result = self._sync()

        self.assertEqual(result["transaction_count"], 1)
        self.assertEqual(result["reconciled_periods_needing_review"], 1)
        with self.runtime.connect() as connection:
            [checkpoint] = ReconciliationCheckpointService(connection).active(account)
        self.assertEqual((checkpoint.status, checkpoint.difference), ("needs_review", 5.0))


if __name__ == "__main__":
    unittest.main()
