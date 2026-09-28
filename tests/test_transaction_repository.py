from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.transaction_repository import TransactionRepository
from services.transaction_service import TransactionService
from tests.support import (
    add_balance_snapshot,
    create_account,
    ensure_domain_schema,
    transaction_summary,
)


class TransactionRepositoryTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(connection: sqlite3.Connection, number: str = "CHEQ-001") -> int:
        return create_account(
            connection, "Chequing", "non_registered", account_number=number, institution="Test"
        )

    def test_create_get_list_and_immutable_domain_object(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = TransactionRepository(connection)

            transaction = repository.create(
                account,
                "2026-09-01",
                125.5,
                description="Deposit",
                balance_after=1125.5,
                category="Income",
                transaction_type="deposit",
            )

            self.assertEqual(transaction.account_id, account)
            self.assertEqual(transaction.amount, 125.5)
            self.assertEqual(repository.get(transaction.id), transaction)
            self.assertEqual(repository.list_for_account(account), [transaction])
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            with self.assertRaises(FrozenInstanceError):
                transaction.amount = 0  # type: ignore[misc]

    def test_optional_transaction_values_are_preserved(self):
        with self._connection() as connection:
            account = self._account(connection)
            transaction = TransactionRepository(connection).create(account, "2026-09-01", -10)

            self.assertIsNone(transaction.raw_transaction_id)
            self.assertIsNone(transaction.description)
            self.assertIsNone(transaction.balance_after)
            self.assertIsNone(transaction.category)
            self.assertEqual(transaction.transaction_type, "unclassified")

    def test_integer_cents_are_the_authoritative_stored_amount(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = TransactionRepository(connection)
            transaction = repository.create(account, "2026-09-01", 12.345)
            stored = connection.execute(
                "SELECT amount, amount_cents FROM transactions WHERE id = ?", (transaction.id,)
            ).fetchone()

            self.assertEqual(stored[1], 1235)
            self.assertEqual(repository.get(transaction.id).amount, 12.35)
            connection.execute(
                "UPDATE transactions SET amount_cents = 1236 WHERE id = ?", (transaction.id,)
            )
            self.assertEqual(repository.get(transaction.id).amount, 12.36)

    def test_account_helpers_and_latest_known_balance(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = TransactionRepository(connection)
            add_balance_snapshot(connection, account, "2026-09-01", 1000)
            repository.create(account, "2026-09-02", 50, balance_after=1050)

            self.assertTrue(repository.account_exists(account))
            self.assertFalse(repository.account_exists(999))
            self.assertEqual(repository.account_asset_kind(account), "account")
            self.assertIsNone(repository.account_asset_kind(999))
            self.assertEqual(
                repository.latest_known_balance(account, "2026-09-02"), ("2026-09-02", 1050.0)
            )
            self.assertIsNone(repository.latest_known_balance(account, "2026-08-31"))


class TransactionServiceTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    def test_service_summary_matches_legacy_contract_for_combined_balances(self):
        with self._connection() as connection:
            first = create_account(connection, "First", "non_registered", account_number="FIRST")
            second = create_account(connection, "Second", "non_registered", account_number="SECOND")
            repository = TransactionRepository(connection)
            repository.create(first, "2026-09-01", 100, balance_after=1100)
            repository.create(second, "2026-09-02", 50, balance_after=2050)

            expected = transaction_summary(connection, account_type="non_registered")
            actual = TransactionService(connection).summary(account_type="non_registered")

            self.assertEqual(actual, expected)
            self.assertEqual(actual[0]["combined_balance_after"], 3150.0)

    def test_recalculate_and_reconcile_preserve_balance_rules(self):
        with self._connection() as connection:
            account = create_account(
                connection, "Calculated", "non_registered", account_number="CALCULATED"
            )
            repository = TransactionRepository(connection)
            repository.create(account, "2026-09-01", 100, description="Deposit")
            repository.create(account, "2026-09-02", -25, description="Purchase")
            repository.create(account, "2026-09-03", 50, description="Refund")
            add_balance_snapshot(connection, account, "2026-09-03", 5000)
            service = TransactionService(connection)

            self.assertEqual(service.recalculate_balances(account), 3)
            self.assertEqual(
                [item.balance_after for item in repository.list_for_account(account)],
                [4975.0, 4950.0, 5000.0],
            )
            result = service.reconcile(account, "2026-09-03", 6000)

            self.assertEqual(result["difference"], 1000.0)
            self.assertEqual(result["status"], "adjusted")
            self.assertEqual(
                [item.balance_after for item in repository.list_for_account(account)],
                [5975.0, 5950.0, 6000.0],
            )

    def test_opening_balance_includes_snapshot_only_accounts(self):
        with self._connection() as connection:
            account = create_account(connection, "New", "non_registered", account_number="NEW")
            add_balance_snapshot(connection, account, "2026-09-01", 1234.56)

            openings = TransactionService(connection).opening_balances(
                account_type="non_registered"
            )

            self.assertEqual(len(openings), 1)
            self.assertEqual(openings[0]["account_id"], account)
            self.assertEqual(openings[0]["balance_after"], 1234.56)

    def test_reconciliation_validation_is_owned_by_service(self):
        with self._connection() as connection:
            account = create_account(
                connection, "Account", "non_registered", account_number="ACCOUNT"
            )
            service = TransactionService(connection)

            for account_id, value_date, amount, message in (
                (account, "bad-date", 1, "Invalid reconciliation date"),
                (account, "2026-09-01", -1, "cannot be negative"),
                (999, "2026-09-01", 1, "Account not found"),
            ):
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    service.reconcile(account_id, value_date, amount)
