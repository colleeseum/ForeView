# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
import json
import sqlite3
import unittest
from contextlib import closing

from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.raw_transaction_repository import RawTransactionRepository
from repositories.transaction_repository import TransactionRepository
from services.database_initialization import ensure_domain_schema
from services.transaction_service import TransactionService

# Each row is (date, amount, stored balance, raw source data or None).
# Expected balances are listed oldest first.
CASES = [
    (
        "calculated rows walk back from the snapshot",
        [
            ("2026-01-10", 100.0, None, None),
            ("2026-02-10", 50.0, None, None),
            ("2026-03-10", -20.0, None, None),
        ],
        [970.0, 1020.0, 1000.0],
        3,
    ),
    (
        "calculated rows below a bank balance continue from that row",
        [
            ("2026-01-10", 10.0, None, None),
            ("2026-02-10", 10.0, 500.0, {"source": "eq_pdf", "balance": 500.0}),
            ("2026-03-10", 5.0, None, None),
        ],
        [490.0, 500.0, 1000.0],
        2,
    ),
    (
        "csv balance column is treated as bank supplied",
        [
            ("2026-01-10", -25.0, None, None),
            ("2026-02-10", 40.0, 300.0, {"Date": "2026-02-10", "Balance": "300.00"}),
        ],
        [260.0, 300.0],
        1,
    ),
    (
        "stored balance without a bank source is recalculated",
        [
            ("2026-01-10", 10.0, 123.0, {"source": "eq_pdf", "balance": None}),
            ("2026-02-10", 20.0, None, None),
        ],
        [980.0, 1000.0],
        2,
    ),
    (
        "consecutive bank balances each reset the running balance",
        [
            ("2026-01-10", 1.0, None, None),
            ("2026-02-10", 2.0, 200.0, {"source": "rbc_gic_pdf", "balance": 200.0}),
            (
                "2026-03-10",
                3.0,
                700.0,
                {"source": "sunlife_transaction_history_pdf", "balance": 700.0},
            ),
        ],
        [198.0, 200.0, 700.0],
        1,
    ),
]


class TransactionBalanceRecalculationTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(connection: sqlite3.Connection) -> int:
        return (
            AccountRepository(connection)
            .create("Savings", "non_registered", account_number="SAV-001", institution="Test")
            .id
        )

    @staticmethod
    def _add_rows(connection: sqlite3.Connection, account_id: int, rows) -> list[int]:
        batch_id = ImportBatchRepository(connection).create(account_id, "rows.csv", "hash").id
        raw_repository = RawTransactionRepository(connection)
        transactions = TransactionRepository(connection)
        ids = []
        for row_number, (transaction_date, amount, balance, raw) in enumerate(rows, start=1):
            raw_id = None
            if raw is not None:
                raw_data = json.dumps(raw, sort_keys=True)
                raw_hash = hashlib.sha256(f"{row_number}:{raw_data}".encode()).hexdigest()
                raw_row = raw_repository.add_if_new(batch_id, row_number, raw_hash, raw_data)
                assert raw_row is not None
                raw_id = raw_row.id
            ids.append(
                transactions.create(
                    account_id,
                    transaction_date,
                    amount,
                    raw_transaction_id=raw_id,
                    balance_after=balance,
                ).id
            )
        return ids

    def test_balances_walk_back_from_latest_snapshot(self):
        for name, rows, expected, expected_updates in CASES:
            with self.subTest(name), self._connection() as connection:
                account = self._account(connection)
                self._add_rows(connection, account, rows)
                BalanceSnapshotRepository(connection).add(account, "2026-03-31", 1000.0)

                updated = TransactionService(connection).recalculate_balances(account)

                balances = [
                    transaction.balance_after
                    for transaction in TransactionRepository(connection).list_for_account(account)
                ]
                self.assertEqual(balances, expected)
                self.assertEqual(updated, expected_updates)

    def test_no_snapshot_leaves_balances_unchanged(self):
        with self._connection() as connection:
            account = self._account(connection)
            self._add_rows(connection, account, [("2026-01-10", 10.0, None, None)])

            self.assertEqual(TransactionService(connection).recalculate_balances(account), 0)
            [transaction] = TransactionRepository(connection).list_for_account(account)
            self.assertIsNone(transaction.balance_after)

    def test_rows_after_the_snapshot_disable_recalculation(self):
        with self._connection() as connection:
            account = self._account(connection)
            self._add_rows(
                connection,
                account,
                [("2026-01-10", 10.0, None, None), ("2026-04-10", 5.0, None, None)],
            )
            BalanceSnapshotRepository(connection).add(account, "2026-03-31", 1000.0)

            self.assertEqual(TransactionService(connection).recalculate_balances(account), 0)
            balances = [
                transaction.balance_after
                for transaction in TransactionRepository(connection).list_for_account(account)
            ]
            self.assertEqual(balances, [None, None])

    def test_institution_balance_policy_controls_statement_rows(self):
        for snapshot_source, expected_balances, expected_updates in (
            ("application", [None, 1000.0], 1),
            ("RBC TFSA PDF", [980.0, 1000.0], 2),
        ):
            with self.subTest(snapshot_source=snapshot_source), self._connection() as connection:
                account = (
                    AccountRepository(connection)
                    .create(
                        "TFSA",
                        "tfsa",
                        account_number="RBC-001",
                        institution="RBC",
                    )
                    .id
                )
                self._add_rows(
                    connection,
                    account,
                    [
                        ("2026-02-10", 10.0, None, {"source": "rbc_tfsa_pdf"}),
                        ("2026-03-10", 20.0, None, None),
                    ],
                )
                BalanceSnapshotRepository(connection).add(
                    account,
                    "2026-03-31",
                    1000.0,
                    source_sheet=snapshot_source,
                )

                updated = TransactionService(connection).recalculate_balances(account)

                balances = [
                    transaction.balance_after
                    for transaction in TransactionRepository(connection).list_for_account(account)
                ]
                self.assertEqual(balances, expected_balances)
                self.assertEqual(updated, expected_updates)

    def test_source_exclusion_does_not_depend_on_account_institution(self):
        with self._connection() as connection:
            account = (
                AccountRepository(connection)
                .create("TFSA", "tfsa", account_number="NO-INSTITUTION", institution=None)
                .id
            )
            self._add_rows(
                connection,
                account,
                [
                    ("2026-02-10", 10.0, None, {"source": "rbc_tfsa_pdf"}),
                    ("2026-03-10", 20.0, None, None),
                ],
            )
            BalanceSnapshotRepository(connection).add(account, "2026-03-31", 1000.0)

            updated = TransactionService(connection).recalculate_balances(account)

            balances = [
                transaction.balance_after
                for transaction in TransactionRepository(connection).list_for_account(account)
            ]
            self.assertEqual(balances, [None, 1000.0])
            self.assertEqual(updated, 1)


if __name__ == "__main__":
    unittest.main()
