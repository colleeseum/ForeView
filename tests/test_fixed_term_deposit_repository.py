# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.fixed_term_deposit_repository import FixedTermDepositRepository
from tests.support import (
    _upsert_imported_gic,
    add_fixed_term_deposit,
    create_account,
    ensure_domain_schema,
)


class FixedTermDepositRepositoryParityTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(connection: sqlite3.Connection) -> int:
        return create_account(
            connection,
            "TFSA GICs",
            "tfsa",
            account_number="TFSA-001",
            institution="Example Bank",
        )

    @staticmethod
    def _rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
        return [
            tuple(row)
            for row in connection.execute(
                """SELECT id, account_id, name, principal, interest_rate, start_date,
                          maturity_date, maturity_value, source_filename, redeemable,
                          renewal_rule
                   FROM fixed_term_deposits ORDER BY id"""
            ).fetchall()
        ]

    def test_create_matches_legacy_and_returns_immutable_complete_row(self):
        arguments = {
            "name": "  Two-year GIC  ",
            "principal": 10000.0,
            "interest_rate": 0.045,
            "start_date": "2026-01-15",
            "maturity_date": "2028-01-15",
            "redeemable": True,
            "renewal_rule": "renew_principal",
            "maturity_value": 10920.25,
            "source_filename": "statement.pdf",
        }
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account = self._account(legacy_connection)
            new_account = self._account(new_connection)

            legacy_id = add_fixed_term_deposit(
                legacy_connection, account_id=legacy_account, **arguments
            )
            repository = FixedTermDepositRepository(new_connection)
            deposit = repository.create(new_account, **arguments)

            self.assertEqual(deposit.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(deposit.name, "Two-year GIC")
            self.assertEqual(deposit.maturity_value, 10920.25)
            self.assertEqual(deposit.source_filename, "statement.pdf")
            self.assertTrue(deposit.redeemable)
            with self.assertRaises(FrozenInstanceError):
                deposit.principal = 0  # type: ignore[misc]

    def test_defaults_and_multiple_deposits_match_legacy(self):
        deposits = (
            ("Later", "2026-01-01", "2028-01-01"),
            ("Earlier", "2026-01-01", "2027-01-01"),
        )
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account = self._account(legacy_connection)
            new_account = self._account(new_connection)
            repository = FixedTermDepositRepository(new_connection)
            for name, start_date, maturity_date in deposits:
                add_fixed_term_deposit(
                    legacy_connection,
                    legacy_account,
                    name,
                    5000.0,
                    0.04,
                    start_date,
                    maturity_date,
                )
                repository.create(
                    new_account,
                    name,
                    5000.0,
                    0.04,
                    start_date,
                    maturity_date,
                )

            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            results = repository.list_for_account(new_account)
            self.assertEqual([item.name for item in results], ["Earlier", "Later"])
            self.assertEqual(results[0].renewal_rule, "cash_at_maturity")
            self.assertFalse(results[0].redeemable)
            self.assertIsNone(results[0].maturity_value)
            self.assertEqual(repository.get(results[0].id), results[0])
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            all_deposits = repository.list_all()
            self.assertEqual([item.name for item in all_deposits], ["Later", "Earlier"])
            self.assertEqual({item.id for item in all_deposits}, {item.id for item in results})

    def test_decimal_text_is_stored_as_authoritative_cents(self):
        with self._connection() as connection:
            account = self._account(connection)
            deposit = FixedTermDepositRepository(connection).create(
                account,
                "Exact GIC",
                "100000000000000.01",
                0.04,
                "2026-01-01",
                "2027-01-01",
                maturity_value="100000000000001.005",
            )

            row = connection.execute(
                """SELECT principal_cents, maturity_value_cents
                   FROM fixed_term_deposits WHERE id = ?""",
                (deposit.id,),
            ).fetchone()
            self.assertEqual(tuple(row), (10000000000000001, 10000000000000101))

    def test_validation_errors_match_legacy_without_writing(self):
        cases = (
            (-1.0, 0.04, "2026-01-01", "2027-01-01"),
            (1000.0, -0.01, "2026-01-01", "2027-01-01"),
            (1000.0, 0.04, "2027-01-01", "2026-01-01"),
        )
        for principal, rate, start_date, maturity_date in cases:
            with self.subTest(
                principal=principal,
                rate=rate,
                start_date=start_date,
                maturity_date=maturity_date,
            ):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_account = self._account(legacy_connection)
                    new_account = self._account(new_connection)
                    legacy_error = self._error(
                        lambda account=legacy_account, value=principal, interest=rate, start=start_date, maturity=maturity_date: (
                            add_fixed_term_deposit(
                                legacy_connection,
                                account,
                                "Invalid",
                                value,
                                interest,
                                start,
                                maturity,
                            )
                        )
                    )
                    new_error = self._error(
                        lambda account=new_account, value=principal, interest=rate, start=start_date, maturity=maturity_date: (
                            FixedTermDepositRepository(new_connection).create(
                                account,
                                "Invalid",
                                value,
                                interest,
                                start,
                                maturity,
                            )
                        )
                    )

                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_legacy_date_comparison_behavior_is_preserved(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account = self._account(legacy_connection)
            new_account = self._account(new_connection)
            legacy_id = add_fixed_term_deposit(
                legacy_connection,
                legacy_account,
                "Unparsed date",
                1000,
                0.04,
                "not-a-date-a",
                "not-a-date-b",
            )
            deposit = FixedTermDepositRepository(new_connection).create(
                new_account,
                "Unparsed date",
                1000,
                0.04,
                "not-a-date-a",
                "not-a-date-b",
            )

            self.assertEqual(deposit.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_import_upsert_insert_and_update_match_legacy(self):
        initial = {
            "certificate": "1234567890",
            "principal": 10000.0,
            "interest_rate": 0.04,
            "start_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "maturity_value": 10400.0,
            "redeemable": False,
        }
        updated = {**initial, "interest_rate": 0.045, "maturity_value": 10450.0, "redeemable": True}
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account = self._account(legacy_connection)
            new_account = self._account(new_connection)
            repository = FixedTermDepositRepository(new_connection)

            legacy_id = _upsert_imported_gic(
                legacy_connection, legacy_account, initial, "initial.pdf"
            )
            deposit = repository.upsert_imported(
                new_account,
                "RBC CPG 1234567890",
                10000.0,
                0.04,
                "2026-01-01",
                "2027-01-01",
                maturity_value=10400.0,
                source_filename="initial.pdf",
                redeemable=False,
            )
            self.assertEqual(deposit.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

            legacy_updated_id = _upsert_imported_gic(
                legacy_connection, legacy_account, updated, "updated.pdf"
            )
            updated_deposit = repository.upsert_imported(
                new_account,
                "RBC CPG 1234567890",
                10000.0,
                0.045,
                "2026-01-01",
                "2027-01-01",
                maturity_value=10450.0,
                source_filename="updated.pdf",
                redeemable=True,
            )

            self.assertEqual(updated_deposit.id, legacy_updated_id)
            self.assertEqual(updated_deposit.id, deposit.id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(updated_deposit.source_filename, "updated.pdf")
            self.assertTrue(updated_deposit.redeemable)

    @staticmethod
    def _error(operation) -> Exception:
        try:
            operation()
        except Exception as error:
            return error
        raise AssertionError("Operation did not raise")
