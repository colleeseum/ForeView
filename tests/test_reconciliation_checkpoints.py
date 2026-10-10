# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Reconciled periods are protected from silent changes by later imports."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from infrastructure.runtime_config import RuntimeConfig
from ingestion.reconciled_period_change import ReconciledPeriodChange
from institutions.questrade.sync import sync_questrade_connection
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from repositories.reconciliation_checkpoint_repository import ReconciliationCheckpointRepository
from repositories.transaction_repository import TransactionRepository
from services.reconciliation_checkpoint_service import ReconciliationCheckpointService
from services.transaction_service import TransactionService
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
        result = reconcile_account_balance(self.connection, self.account, "20260131", 600.0)

        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(result["date"], "2026-01-31")
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

    def test_legacy_iso_import_into_reconciled_period_is_refused(self):
        self._reconcile_january()
        self.connection.commit()
        transactions, batches = self._count(), self._count("import_batches")

        for transaction_date in ("20260125", "2026-W04-7"):
            with self.subTest(transaction_date=transaction_date):
                with self.assertRaises(ReconciledPeriodChange) as refused:
                    import_csv_transactions(
                        self.connection,
                        self.account,
                        f"late-{transaction_date}.csv",
                        _csv(f"{transaction_date},Refund,50,650\n"),
                    )

                self.assertEqual(refused.exception.reconciled_through, "2026-01-31")
                self.assertEqual(refused.exception.transaction_count, 1)
                self.assertEqual(
                    (self._count(), self._count("import_batches")), (transactions, batches)
                )

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

    def test_confirmed_legacy_iso_import_flags_the_period(self):
        self._reconcile_january()

        import_csv_transactions(
            self.connection,
            self.account,
            "late-compact.csv",
            _csv("20260125,Refund,50,650\n"),
            allow_reconciled=True,
        )

        [flagged] = self.checkpoints.active(self.account)
        self.assertEqual((flagged.status, flagged.difference), ("needs_review", 50.0))

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

    def test_correcting_reconciliation_retires_equivalent_legacy_date_keys(self):
        for legacy_date in ("20260131", "2026-W05-6"):
            with self.subTest(legacy_date=legacy_date):
                account = create_account(
                    self.connection,
                    f"Legacy {legacy_date}",
                    "non_registered",
                    account_number=f"LEGACY-{legacy_date}",
                    institution="Test",
                )
                import_csv_transactions(
                    self.connection,
                    account,
                    f"{legacy_date}.csv",
                    b"Date,Description,Amount\n2026-01-05,Pay,1000\n2026-01-20,Rent,-400\n",
                )
                BalanceSnapshotRepository(self.connection).add(
                    account,
                    legacy_date,
                    650,
                    source_sheet="Manual reconciliation",
                    source_address="transactions",
                )
                TransactionService(self.connection).recalculate_balances(account)
                ReconciliationCheckpointRepository(self.connection).create(
                    account,
                    period_start=None,
                    reconciled_through=legacy_date,
                    closing_balance=650,
                    net_change=600,
                    transaction_count=2,
                    source="manual",
                )

                corrected = reconcile_account_balance(self.connection, account, "2026-01-31", 600)

                self.assertEqual(
                    (corrected["status"], corrected["difference"]), ("reconciled", None)
                )
                [active] = self.checkpoints.active(account)
                self.assertEqual(active.reconciled_through, "2026-01-31")
                manual_dates = [
                    item.snapshot_date
                    for item in BalanceSnapshotRepository(self.connection).list_for_account(account)
                    if item.source_sheet == "Manual reconciliation"
                ]
                self.assertEqual(manual_dates, ["2026-01-31"])

    def test_legacy_checkpoint_dates_use_calendar_order_for_later_periods(self):
        ReconciliationCheckpointRepository(self.connection).create(
            self.account,
            period_start=None,
            reconciled_through="20260131",
            closing_balance=600,
            net_change=600,
            transaction_count=2,
            source="manual",
        )

        later = self.checkpoints.record_known_balance(self.account, "20260228", 600)

        self.assertEqual(later.period_start, "2026-02-01")
        self.assertEqual(later.reconciled_through, "2026-02-28")
        self.assertEqual(self.checkpoints.locked_through(self.account), "2026-02-28")

    def test_legacy_non_manual_snapshot_is_used_for_reconciliation_comparison(self):
        account = create_account(
            self.connection,
            "Legacy anchor",
            "non_registered",
            account_number="LEGACY-ANCHOR",
            institution="Test",
        )
        BalanceSnapshotRepository(self.connection).add(account, "20260115", 1000)

        result = reconcile_account_balance(self.connection, account, "20260131", 900)

        self.assertEqual((result["status"], result["difference"]), ("adjusted", -100.0))
        self.assertEqual(self.checkpoints.active(account), [])

    def test_reconciliation_rebuild_uses_latest_snapshot_by_calendar_date(self):
        account = create_account(
            self.connection,
            "Legacy rebuild",
            "non_registered",
            account_number="LEGACY-REBUILD",
            institution="Test",
        )
        BalanceSnapshotRepository(self.connection).add(account, "20260115", 1000)
        transaction = TransactionRepository(self.connection).create(account, "20260120", -100)

        result = reconcile_account_balance(self.connection, account, "2026-01-31", 900)

        self.assertEqual((result["status"], result["difference"]), ("adjusted", -100.0))
        self.assertEqual(
            TransactionRepository(self.connection).get(transaction.id).balance_after, 900
        )

    def test_checkpoint_totals_include_legacy_transaction_date_forms(self):
        account = create_account(
            self.connection,
            "Legacy checkpoint",
            "non_registered",
            account_number="LEGACY-CHECKPOINT",
            institution="Test",
        )
        TransactionRepository(self.connection).create(account, "20260120", 600, balance_after=600)

        result = reconcile_account_balance(self.connection, account, "2026-01-31", 600)

        self.assertEqual(result["status"], "reconciled")
        [checkpoint] = self.checkpoints.active(account)
        self.assertEqual((checkpoint.net_change, checkpoint.transaction_count), (600, 1))

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
