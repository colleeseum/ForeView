# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

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

    def test_latest_known_balance_compares_legacy_iso_forms_by_calendar_date(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = TransactionRepository(connection)
            add_balance_snapshot(connection, account, "20260115", 1000)
            repository.create(account, "2026-W03-5", 50, balance_after=1050)

            self.assertEqual(
                repository.latest_known_balance(account, "2026-01-15"),
                ("2026-01-15", 1000.0),
            )
            self.assertEqual(
                repository.latest_known_balance(account, "2026-01-31"),
                ("2026-01-16", 1050.0),
            )

    def test_reconciliation_queries_compare_legacy_iso_forms_by_calendar_date(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = TransactionRepository(connection)
            add_balance_snapshot(connection, account, "20260115", 1000)
            add_balance_snapshot(connection, account, "2026-01-31", 900)
            repository.create(account, "2026-W03-5", 50)
            repository.create(account, "20260120", -100)
            repository.create(account, "not-a-date", 500)

            self.assertEqual(repository.latest_snapshot(account).snapshot_date, "2026-01-31")
            self.assertEqual(repository.period_totals(account, "2026-01-16", "20260131"), (-50, 2))
            self.assertEqual(
                repository.amounts_between(account, "20260116", "2026-01-31"), [50, -100]
            )
            self.assertEqual(
                [
                    row.transaction_date
                    for row in repository.rows_for_balance_recalculation(account)
                ],
                ["2026-01-20", "2026-01-16"],
            )

    def test_summary_queries_order_and_canonicalize_legacy_iso_forms(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = TransactionRepository(connection)
            add_balance_snapshot(connection, account, "2026-W03-5", 50)
            repository.create(account, "20260120", 100, balance_after=100)
            repository.create(account, "2026-01-25", 50, balance_after=150)

            self.assertEqual(
                [row["transaction_date"] for row in repository.summary_rows(None, None)],
                ["2026-01-20", "2026-01-25"],
            )
            self.assertEqual(
                [event[2] for event in repository.balance_events()],
                ["2026-01-16", "2026-01-20", "2026-01-25"],
            )


class TransactionServiceTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    def test_combined_balance_uses_latest_same_day_snapshot_then_transaction(self):
        with self._connection() as connection:
            account = create_account(connection, "Legacy", "non_registered", account_number="L")
            repository = TransactionRepository(connection)
            repository.create(account, "2026-01-30", 0, balance_after=1000)
            add_balance_snapshot(connection, account, "20260131", 1000)
            add_balance_snapshot(connection, account, "2026-01-31", 900)
            self.assertEqual([event[3] for event in repository.balance_events()], [1000, 1000, 900])
            self.assertEqual(
                TransactionService(connection).summary()[0]["combined_balance_after"], 900
            )
            repository.create(account, "2026-W05-6", 50, balance_after=950)
            self.assertEqual(
                [event[3] for event in repository.balance_events()], [1000, 1000, 900, 950]
            )
            self.assertEqual(
                TransactionService(connection).summary()[0]["combined_balance_after"], 950
            )

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

    def test_service_summary_uses_calendar_order_for_legacy_date_forms(self):
        with self._connection() as connection:
            account = create_account(
                connection, "Legacy", "non_registered", account_number="LEGACY"
            )
            repository = TransactionRepository(connection)
            repository.create(account, "not-a-date", 500, balance_after=500)
            repository.create(account, "20260120", 100, balance_after=100)
            repository.create(account, "2026-01-25", 50, balance_after=150)

            summary = TransactionService(connection).summary()

            self.assertEqual(
                [(row["transaction_date"], row["combined_balance_after"]) for row in summary],
                [("2026-01-25", 150), ("2026-01-20", 100), ("not-a-date", 0)],
            )

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

    def test_opening_balances_use_semantic_order_for_legacy_dates(self):
        with self._connection() as connection:
            transaction_account = create_account(
                connection,
                "Transactions",
                "non_registered",
                account_number="TRANSACTIONS",
            )
            snapshot_account = create_account(
                connection,
                "Snapshots",
                "non_registered",
                account_number="SNAPSHOTS",
            )
            repository = TransactionRepository(connection)
            repository.create(transaction_account, "not-a-date", 50, balance_after=550)
            repository.create(transaction_account, "2026-01-20", 100, balance_after=100)
            add_balance_snapshot(connection, snapshot_account, "not-a-date", 500)
            add_balance_snapshot(connection, snapshot_account, "2026-01-20", 100)

            openings = TransactionService(connection).opening_balances(
                account_type="non_registered"
            )
            by_account = {int(row["account_id"]): row for row in openings}

            self.assertEqual(
                (
                    by_account[transaction_account]["transaction_date"],
                    by_account[transaction_account]["balance_after"],
                ),
                ("not-a-date", 500.0),
            )
            self.assertEqual(
                (
                    by_account[snapshot_account]["transaction_date"],
                    by_account[snapshot_account]["balance_after"],
                ),
                ("not-a-date", 500.0),
            )

    def test_snapshot_only_opening_dates_are_canonical(self):
        for legacy_date in ("20260115", "2026-W03-4"):
            with self.subTest(legacy_date=legacy_date), self._connection() as connection:
                account = create_account(
                    connection, "Legacy", "non_registered", account_number="LEGACY"
                )
                add_balance_snapshot(connection, account, legacy_date, 1000)
                add_balance_snapshot(connection, account, "2026-02-01", 900)

                [opening] = TransactionService(connection).opening_balances(account_id=account)

                self.assertEqual(opening["transaction_date"], "2026-01-15")
                self.assertEqual(opening["balance_after"], 1000)

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
