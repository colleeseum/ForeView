# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.account_repository import AccountRepository
from tests.support import create_account, ensure_domain_schema, update_account


class AccountRepositoryParityTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
        return [
            tuple(row)
            for row in connection.execute(
                """SELECT id, name, account_number, account_type, institution,
                          tax_treatment, current_interest_rate, asset_kind,
                          parent_account_id, balance_includes_children, start_date,
                          maturity_date, maturity_value, principal, redeemable,
                          external_provider, external_account_id
                   FROM accounts ORDER BY id"""
            ).fetchall()
        ]

    def test_create_regular_account_matches_legacy(self):
        arguments = {
            "name": "  Primary TFSA  ",
            "account_type": "tfsa",
            "account_number": "  TFSA-001  ",
            "institution": "Example Bank",
            "external_provider": "example",
            "external_account_id": "external-1",
        }
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_account(legacy_connection, **arguments)
            account = AccountRepository(new_connection).create(**arguments)

            self.assertEqual(account.id, legacy_id)
            self.assertEqual(account.name, "Primary TFSA")
            self.assertEqual(account.account_number, "TFSA-001")
            self.assertEqual(account.tax_treatment, "tax_free")
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            with self.assertRaises(FrozenInstanceError):
                account.name = "Changed"  # type: ignore[misc]

    def test_create_gic_and_fallback_identity_match_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_parent = create_account(
                legacy_connection, None, "rrsp", account_number="RRSP-001"
            )
            new_parent = AccountRepository(new_connection).create(
                None, "rrsp", account_number="RRSP-001"
            )
            arguments = {
                "name": "  Two year GIC  ",
                "account_type": "rrsp",
                "account_number": "gic:temporary",
                "institution": "Example Bank",
                "asset_kind": "gic",
                "start_date": "2026-01-01",
                "maturity_date": "2028-01-01",
                "maturity_value": 10800.0,
                "principal": 10000.0,
                "redeemable": True,
            }
            legacy_id = create_account(
                legacy_connection, parent_account_id=legacy_parent, **arguments
            )
            account = AccountRepository(new_connection).create(
                parent_account_id=new_parent.id, **arguments
            )

            self.assertEqual(account.id, legacy_id)
            self.assertEqual(
                account.account_number,
                f"gic:{new_parent.id}:Two year GIC:2028-01-01",
            )
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_decimal_text_is_converted_directly_to_authoritative_cents(self):
        with self._connection() as connection:
            parent = AccountRepository(connection).create(
                "RRSP", "rrsp", account_number="RRSP-DECIMAL"
            )
            account = AccountRepository(connection).create(
                "Large GIC",
                "rrsp",
                account_number="GIC-DECIMAL",
                asset_kind="gic",
                parent_account_id=parent.id,
                principal="100000000000000.01",
                maturity_value="100000000000001.005",
            )

            row = connection.execute(
                "SELECT principal_cents, maturity_value_cents FROM accounts WHERE id = ?",
                (account.id,),
            ).fetchone()

            self.assertEqual(tuple(row), (10000000000000001, 10000000000000101))

    def test_create_validation_errors_match_legacy(self):
        cases = (
            {"name": None, "account_type": "tfsa", "account_number": ""},
            {
                "name": "Invalid",
                "account_type": "tfsa",
                "account_number": "INVALID",
                "asset_kind": "crypto",
            },
            {
                "name": "Unlinked GIC",
                "account_type": "tfsa",
                "account_number": "GIC-1",
                "asset_kind": "gic",
            },
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_error = self._error(
                        lambda arguments=arguments: create_account(legacy_connection, **arguments)
                    )
                    new_error = self._error(
                        lambda arguments=arguments: AccountRepository(new_connection).create(
                            **arguments
                        )
                    )
                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_update_with_and_without_category_matches_legacy(self):
        for category in (None, "rrsp"):
            with self.subTest(category=category):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_id = create_account(
                        legacy_connection,
                        "Original",
                        "tfsa",
                        account_number="ORIGINAL",
                        institution="Old Bank",
                    )
                    repository = AccountRepository(new_connection)
                    account = repository.create(
                        "Original",
                        "tfsa",
                        account_number="ORIGINAL",
                        institution="Old Bank",
                    )
                    arguments = {
                        "name": "  Updated  ",
                        "account_number": "  UPDATED  ",
                        "institution": "New Bank",
                        "category": category,
                        "external_provider": "provider",
                        "external_account_id": "external",
                        "redeemable": True,
                    }
                    legacy_result = update_account(legacy_connection, legacy_id, **arguments)
                    new_result = repository.update(account.id, **arguments)

                    self.assertIsNone(legacy_result)
                    self.assertIsNone(new_result)
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
                    updated = repository.get(account.id)
                    self.assertIsNotNone(updated)
                    self.assertEqual(updated.account_type, category or "tfsa")
                    self.assertEqual(updated.name, "Updated")

    def test_update_validation_and_missing_id_match_legacy(self):
        invalid_cases = (
            {"account_number": "", "asset_kind": None},
            {"account_number": "A", "asset_kind": "crypto"},
            {"account_number": "G", "asset_kind": "gic"},
        )
        for arguments in invalid_cases:
            with self.subTest(arguments=arguments):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    common = {"name": "Account", "institution": None, **arguments}
                    legacy_error = self._error(
                        lambda common=common: update_account(legacy_connection, 999, **common)
                    )
                    new_error = self._error(
                        lambda common=common: AccountRepository(new_connection).update(
                            999, **common
                        )
                    )
                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))

        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_result = update_account(
                legacy_connection,
                999,
                name="Missing",
                account_number="MISSING",
                institution=None,
            )
            repository = AccountRepository(new_connection)
            new_result = repository.update(
                999, name="Missing", account_number="MISSING", institution=None
            )
            self.assertIsNone(legacy_result)
            self.assertIsNone(new_result)
            self.assertIsNone(repository.get(999))
            self.assertIsNone(repository.get(None))
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    @staticmethod
    def _error(operation) -> Exception:
        try:
            operation()
        except Exception as error:
            return error
        raise AssertionError("Operation did not raise")
