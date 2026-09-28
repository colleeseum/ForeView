from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.import_batch_repository import ImportBatchRepository
from repositories.statement_reconciliation_repository import StatementReconciliationRepository
from tests.support import create_account, ensure_domain_schema


class StatementReconciliationRepositoryTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(connection: sqlite3.Connection, number: str = "CHEQ-001") -> int:
        return create_account(connection, "Chequing", "cash", account_number=number)

    @staticmethod
    def _batch(connection: sqlite3.Connection, account_id: int, suffix: str = "1") -> int:
        return (
            ImportBatchRepository(connection)
            .create(
                account_id,
                f"statement-{suffix}.pdf",
                f"statement-hash-{suffix}",
            )
            .id
        )

    @staticmethod
    def _arguments(account_id: int, batch_id: int) -> dict[str, object]:
        return {
            "account_id": account_id,
            "import_batch_id": batch_id,
            "statement_start": "2026-08-01",
            "statement_end": "2026-08-31",
            "opening_balance": 1000.0,
            "closing_balance": 1250.0,
            "statement_deposits": 400.0,
            "statement_withdrawals": 150.0,
            "csv_transaction_count": 7,
            "csv_net_change": 250.0,
            "difference": 0.0,
            "status": "reconciled",
        }

    def test_create_and_retrieve_immutable_complete_row(self):
        with self._connection() as connection:
            account = self._account(connection)
            batch = self._batch(connection, account)
            repository = StatementReconciliationRepository(connection)

            reconciliation = repository.create(**self._arguments(account, batch))  # type: ignore[arg-type]

            self.assertEqual(reconciliation.account_id, account)
            self.assertEqual(reconciliation.import_batch_id, batch)
            self.assertEqual(reconciliation.closing_balance, 1250.0)
            self.assertEqual(reconciliation.csv_transaction_count, 7)
            self.assertEqual(reconciliation.status, "reconciled")
            self.assertTrue(reconciliation.created_at)
            self.assertEqual(repository.get(reconciliation.id), reconciliation)
            self.assertEqual(repository.get_by_import_batch(batch), reconciliation)
            self.assertEqual(repository.list_for_account(account), [reconciliation])
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            self.assertIsNone(repository.get_by_import_batch(999))
            with self.assertRaises(FrozenInstanceError):
                reconciliation.status = "difference"  # type: ignore[misc]

    def test_optional_amounts_are_preserved(self):
        with self._connection() as connection:
            account = self._account(connection)
            batch = self._batch(connection, account)
            arguments = self._arguments(account, batch)
            for field in (
                "opening_balance",
                "closing_balance",
                "statement_deposits",
                "statement_withdrawals",
                "csv_net_change",
                "difference",
            ):
                arguments[field] = None

            reconciliation = StatementReconciliationRepository(connection).create(
                **arguments  # type: ignore[arg-type]
            )

            self.assertIsNone(reconciliation.opening_balance)
            self.assertIsNone(reconciliation.closing_balance)
            self.assertIsNone(reconciliation.difference)

    def test_account_period_uniqueness_is_preserved(self):
        with self._connection() as connection:
            account = self._account(connection)
            first_batch = self._batch(connection, account, "1")
            second_batch = self._batch(connection, account, "2")
            repository = StatementReconciliationRepository(connection)
            repository.create(**self._arguments(account, first_batch))  # type: ignore[arg-type]
            duplicate = self._arguments(account, second_batch)

            with self.assertRaises(sqlite3.IntegrityError) as error:
                repository.create(**duplicate)  # type: ignore[arg-type]

            self.assertIn(
                "statement_reconciliations.account_id",
                str(error.exception),
            )

    def test_same_period_is_allowed_for_different_accounts(self):
        with self._connection() as connection:
            first_account = self._account(connection, "CHEQ-001")
            second_account = self._account(connection, "CHEQ-002")
            first_batch = self._batch(connection, first_account, "1")
            second_batch = self._batch(connection, second_account, "2")
            repository = StatementReconciliationRepository(connection)

            first = repository.create(
                **self._arguments(first_account, first_batch)  # type: ignore[arg-type]
            )
            second = repository.create(
                **self._arguments(second_account, second_batch)  # type: ignore[arg-type]
            )

            self.assertNotEqual(first.id, second.id)

    def test_unparsed_dates_and_arbitrary_status_are_preserved(self):
        with self._connection() as connection:
            account = self._account(connection)
            batch = self._batch(connection, account)
            arguments = self._arguments(account, batch)
            arguments["statement_start"] = "not-a-date-a"
            arguments["statement_end"] = "not-a-date-b"
            arguments["status"] = "custom"

            reconciliation = StatementReconciliationRepository(connection).create(
                **arguments  # type: ignore[arg-type]
            )

            self.assertEqual(reconciliation.statement_start, "not-a-date-a")
            self.assertEqual(reconciliation.status, "custom")
