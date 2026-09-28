"""Stored Questrade activity is re-keyed so upgrading does not import it again."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.runtime_config import RuntimeConfig
from institutions.questrade.sync import sync_questrade_connection
from repositories.account_repository import AccountRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from repositories.raw_transaction_repository import RawTransactionRepository
from repositories.transaction_repository import TransactionRepository
from services.database_initialization import ensure_domain_schema

DIVIDEND = {"transactionDate": "2026-09-01T12:00:00Z", "netAmount": 25.0, "type": "Dividend"}
DEPOSIT = {"transactionDate": "2026-08-01T12:00:00Z", "netAmount": 500.0, "type": "Deposit"}


class QuestradeActivityIdentityMigrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.runtime = RuntimeConfig(Path(directory.name))
        self.connection = self.runtime.connect()
        self.addCleanup(self.connection.close)
        ensure_domain_schema(self.connection)
        self.account = (
            AccountRepository(self.connection)
            .create(
                "Questrade QT-1",
                "tfsa",
                account_number="QT-1",
                institution="Questrade",
                external_provider="questrade",
                external_account_id="QT-1",
            )
            .id
        )
        QuestradeAuthorizationRepository(self.connection).add_if_absent(
            "alex",
            access_token="unused",
            refresh_token="unused",
            api_server="https://api01.iq.questrade.com/",
        )
        self.connection.commit()

    def _store_legacy_activity(self, login: str, *activities: dict) -> int:
        """Store activity exactly as the sync did before activity identity changed."""
        batch = ImportBatchRepository(self.connection).create(
            self.account, "Questrade activities QT-1", f"questrade:{login}:QT-1:activities"
        )
        raw_transactions = RawTransactionRepository(self.connection)
        for row_number, activity in enumerate(activities, start=1):
            raw_data = json.dumps(
                {"source": "questrade", "connection": login, "activity": activity},
                sort_keys=True,
            )
            legacy_hash = hashlib.sha256(raw_data.encode()).hexdigest()
            raw_id = raw_transactions.add(batch.id, row_number, legacy_hash, raw_data)
            TransactionRepository(self.connection).create(
                self.account,
                activity["transactionDate"][:10],
                activity["netAmount"],
                raw_transaction_id=raw_id,
                description=activity["type"],
                category=activity["type"],
                transaction_type=activity["type"].lower(),
            )
        self.connection.commit()
        return batch.id

    def _migrate_again(self):
        self.connection.execute("DELETE FROM schema_migrations WHERE version = 4")
        self.connection.commit()
        ensure_domain_schema(self.connection)

    def _sync(self, *activities: dict):
        served = []

        def api(_authorization, path):
            if path == "/v1/accounts":
                return {"accounts": [{"number": "QT-1", "type": "TFSA"}]}
            if "/activities?" in path and not served:
                served.append(path)
                return {"activities": list(activities)}
            return {}

        return sync_questrade_connection(
            self.runtime.connect,
            "alex",
            api_getter=api,
            refresh_expiring=lambda _connection: None,
            refresh_authorization=lambda _connection, _authorization: None,
            history_start="2026-01-01",
        )

    def _count(self, table: str) -> int:
        return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608

    def test_upgraded_activity_is_recognised_by_the_next_sync(self):
        self._store_legacy_activity("alex", DIVIDEND, DEPOSIT)
        self._migrate_again()

        result = self._sync(DIVIDEND, DEPOSIT)

        self.assertEqual(result["transaction_count"], 0)
        self.assertEqual(self._count("transactions"), 2)
        batch = self.connection.execute(
            "SELECT file_hash, row_count FROM import_batches"
        ).fetchone()
        self.assertEqual(tuple(batch), ("questrade:QT-1:activities", 2))

    def test_activity_from_two_logins_merges_into_one_account_batch(self):
        self._store_legacy_activity("alex", DIVIDEND)
        self._store_legacy_activity("alex-old", DEPOSIT)
        self._migrate_again()

        result = self._sync(DIVIDEND, DEPOSIT)

        self.assertEqual(result["transaction_count"], 0)
        self.assertEqual(self._count("import_batches"), 1)
        self.assertEqual(self._count("raw_transactions"), 2)

    def test_existing_duplicates_across_logins_are_left_untouched(self):
        self._store_legacy_activity("alex", DIVIDEND)
        self._store_legacy_activity("alex-old", DIVIDEND)
        self._migrate_again()

        result = self._sync(DIVIDEND)

        self.assertEqual(result["transaction_count"], 0)
        self.assertEqual(self._count("transactions"), 2)
        self.assertEqual(self._count("import_batches"), 2)


if __name__ == "__main__":
    unittest.main()
