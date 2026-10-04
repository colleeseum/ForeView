# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from tests.support import add_balance_snapshot, create_account, ensure_domain_schema


class BalanceSnapshotRepositoryParityTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(connection: sqlite3.Connection) -> int:
        return create_account(connection, "Savings", "cash", account_number="SAV-001")

    @staticmethod
    def _rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
        return [
            tuple(row)
            for row in connection.execute(
                """SELECT id, account_id, snapshot_date, amount, contribution, lock_date,
                          maturity_date, interest_rate, source_sheet, source_address
                   FROM balance_snapshots ORDER BY id"""
            ).fetchall()
        ]

    def test_add_matches_legacy_and_returns_immutable_complete_row(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account = self._account(legacy_connection)
            new_account = self._account(new_connection)

            legacy_result = add_balance_snapshot(
                legacy_connection,
                legacy_account,
                "2026-09-27",
                1234.56,
                0.0275,
                source_sheet="Statement",
                source_address="balance:1",
            )
            repository = BalanceSnapshotRepository(new_connection)
            new_result = repository.add(
                new_account,
                "2026-09-27",
                1234.56,
                0.0275,
                source_sheet="Statement",
                source_address="balance:1",
            )

            self.assertIsNone(legacy_result)
            self.assertIsNone(new_result)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            snapshot = repository.list_for_account(new_account)[0]
            self.assertEqual(snapshot.amount, 1234.56)
            self.assertEqual(snapshot.interest_rate, 0.0275)
            self.assertIsNone(snapshot.contribution)
            with self.assertRaises(FrozenInstanceError):
                snapshot.amount = 0  # type: ignore[misc]

    def test_default_source_and_replacement_match_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account = self._account(legacy_connection)
            new_account = self._account(new_connection)
            repository = BalanceSnapshotRepository(new_connection)

            add_balance_snapshot(legacy_connection, legacy_account, "2026-09-27", 100)
            repository.add(new_account, "2026-09-27", 100)
            add_balance_snapshot(legacy_connection, legacy_account, "2026-09-27", 125)
            repository.add(new_account, "2026-09-27", 125)

            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            snapshots = repository.list_for_account(new_account)
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].amount, 125)
            self.assertEqual(snapshots[0].source_sheet, "application")
            self.assertEqual(snapshots[0].source_address, "manual")
            self.assertEqual(repository.get(snapshots[0].id), snapshots[0])
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))

    def test_same_date_with_different_source_is_not_replaced(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account = self._account(legacy_connection)
            new_account = self._account(new_connection)
            repository = BalanceSnapshotRepository(new_connection)
            for source_address, amount in (("first", 100.0), ("second", 200.0)):
                add_balance_snapshot(
                    legacy_connection,
                    legacy_account,
                    "2026-09-27",
                    amount,
                    source_address=source_address,
                )
                repository.add(
                    new_account,
                    "2026-09-27",
                    amount,
                    source_address=source_address,
                )

            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(len(repository.list_for_account(new_account)), 2)

    def test_decimal_text_does_not_pass_through_binary_float(self):
        with self._connection() as connection:
            account = self._account(connection)
            BalanceSnapshotRepository(connection).add(
                account,
                "2026-09-27",
                "100000000000000.01",
                contribution="0.005",
            )

            row = connection.execute(
                """SELECT amount_cents, contribution_cents
                   FROM balance_snapshots WHERE account_id = ?""",
                (account,),
            ).fetchone()

            self.assertEqual(tuple(row), (10000000000000001, 1))

    def test_reads_importer_owned_snapshot_fields(self):
        with self._connection() as connection:
            account = self._account(connection)
            cursor = connection.execute(
                """INSERT INTO balance_snapshots(
                       account_id, snapshot_date, amount, contribution, lock_date,
                       maturity_date, interest_rate, source_sheet, source_address
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account,
                    "2026-09-27",
                    10500.0,
                    500.0,
                    "2026-01-01",
                    "2027-01-01",
                    0.04,
                    "Imported statement",
                    "row:42",
                ),
            )

            snapshot = BalanceSnapshotRepository(connection).get(cursor.lastrowid)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(snapshot.contribution, 500.0)
            self.assertEqual(snapshot.lock_date, "2026-01-01")
            self.assertEqual(snapshot.maturity_date, "2027-01-01")
            self.assertEqual(snapshot.source_address, "row:42")

    def test_validation_errors_match_legacy_without_writing(self):
        cases = ((-1.0, None), (1.0, -0.01))
        for amount, interest_rate in cases:
            with self.subTest(amount=amount, interest_rate=interest_rate):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_account = self._account(legacy_connection)
                    new_account = self._account(new_connection)
                    legacy_error = self._error(
                        lambda account=legacy_account, value=amount, rate=interest_rate: (
                            add_balance_snapshot(
                                legacy_connection,
                                account,
                                "2026-09-27",
                                value,
                                rate,
                            )
                        )
                    )
                    new_error = self._error(
                        lambda account=new_account, value=amount, rate=interest_rate: (
                            BalanceSnapshotRepository(new_connection).add(
                                account,
                                "2026-09-27",
                                value,
                                rate,
                            )
                        )
                    )

                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    @staticmethod
    def _error(operation) -> Exception:
        try:
            operation()
        except Exception as error:
            return error
        raise AssertionError("Operation did not raise")
