from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.account_ownership_repository import AccountOwnershipRepository
from tests.support import create_account, create_person, ensure_domain_schema, set_account_owners


class AccountOwnershipRepositoryParityTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _fixture(connection: sqlite3.Connection) -> tuple[int, int, int]:
        first = create_person(connection, "First Owner")
        second = create_person(connection, "Second Owner")
        account = create_account(connection, "Joint Account", "tfsa", account_number="JOINT-001")
        return account, first, second

    @staticmethod
    def _rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
        return [
            tuple(row)
            for row in connection.execute(
                """SELECT account_id, person_id, ownership_share
                   FROM account_owners ORDER BY account_id, person_id"""
            ).fetchall()
        ]

    def test_joint_ownership_matches_legacy_and_returns_immutable_objects(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account, legacy_first, legacy_second = self._fixture(legacy_connection)
            new_account, new_first, new_second = self._fixture(new_connection)

            legacy_result = set_account_owners(
                legacy_connection,
                legacy_account,
                [(legacy_first, 0.4), (legacy_second, 0.6)],
            )
            repository = AccountOwnershipRepository(new_connection)
            new_result = repository.replace(new_account, [(new_first, 0.4), (new_second, 0.6)])

            self.assertIsNone(legacy_result)
            self.assertIsNone(new_result)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            ownership = repository.list_for_account(new_account)
            self.assertEqual([item.share for item in ownership], [0.4, 0.6])
            with self.assertRaises(FrozenInstanceError):
                ownership[0].share = 1.0  # type: ignore[misc]

    def test_replacement_removes_previous_owners_like_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account, legacy_first, legacy_second = self._fixture(legacy_connection)
            new_account, new_first, new_second = self._fixture(new_connection)
            set_account_owners(legacy_connection, legacy_account, [(legacy_first, 1.0)])
            new_repository = AccountOwnershipRepository(new_connection)
            new_repository.replace(new_account, [(new_first, 1.0)])

            set_account_owners(legacy_connection, legacy_account, [(legacy_second, 1.0)])
            new_repository.replace(new_account, [(new_second, 1.0)])

            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(
                new_repository.list_for_account(new_account)[0].person_id,
                new_second,
            )

    def test_validation_errors_and_tolerance_match_legacy(self):
        invalid_owners = (
            [],
            [(1, 0.6), (2, 0.6)],
            [(1, -0.1), (2, 1.1)],
        )
        for owners in invalid_owners:
            with self.subTest(owners=owners):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_account, legacy_first, _ = self._fixture(legacy_connection)
                    new_account, new_first, _ = self._fixture(new_connection)
                    set_account_owners(legacy_connection, legacy_account, [(legacy_first, 1.0)])
                    AccountOwnershipRepository(new_connection).replace(
                        new_account, [(new_first, 1.0)]
                    )

                    legacy_error = self._error(
                        lambda owners=owners, legacy_account=legacy_account: set_account_owners(
                            legacy_connection, legacy_account, owners
                        )
                    )
                    new_error = self._error(
                        lambda owners=owners, new_account=new_account: AccountOwnershipRepository(
                            new_connection
                        ).replace(new_account, owners)
                    )
                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account, legacy_first, legacy_second = self._fixture(legacy_connection)
            new_account, new_first, new_second = self._fixture(new_connection)
            set_account_owners(
                legacy_connection,
                legacy_account,
                [(legacy_first, 0.5), (legacy_second, 0.5000005)],
            )
            AccountOwnershipRepository(new_connection).replace(
                new_account, [(new_first, 0.5), (new_second, 0.5000005)]
            )
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_duplicate_owner_integrity_failure_matches_legacy_side_effects(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_account, legacy_first, _ = self._fixture(legacy_connection)
            new_account, new_first, _ = self._fixture(new_connection)
            legacy_error = self._error(
                lambda: set_account_owners(
                    legacy_connection,
                    legacy_account,
                    [(legacy_first, 0.5), (legacy_first, 0.5)],
                )
            )
            new_error = self._error(
                lambda: AccountOwnershipRepository(new_connection).replace(
                    new_account, [(new_first, 0.5), (new_first, 0.5)]
                )
            )

            self.assertIsInstance(legacy_error, sqlite3.IntegrityError)
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
