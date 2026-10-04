# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from collections.abc import Callable
from contextlib import closing

from domain.person import Person
from repositories.person_repository import PersonRepository
from tests.support import _person_id, create_person, ensure_domain_schema, update_person_birth_date


class PersonRepositoryParityTests(unittest.TestCase):
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
                "SELECT id, name, birth_date FROM people ORDER BY id"
            ).fetchall()
        ]

    def test_create_matches_legacy_function(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_person(legacy_connection, "  Casey Example  ", "1980-04-03")
            person = PersonRepository(new_connection).create("  Casey Example  ", "1980-04-03")

            self.assertEqual(person, Person(legacy_id, "Casey Example", "1980-04-03"))
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_empty_birth_date_matches_legacy_null_storage(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            create_person(legacy_connection, "Casey", "")
            person = PersonRepository(new_connection).create("Casey", "")

            self.assertIsNone(person.birth_date)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_validation_and_duplicate_errors_match_legacy(self):
        operations: tuple[
            tuple[Callable[[sqlite3.Connection], object], Callable[[sqlite3.Connection], object]],
            ...,
        ] = (
            (
                lambda connection: create_person(connection, "   "),
                lambda connection: PersonRepository(connection).create("   "),
            ),
            (
                lambda connection: self._create_duplicate_legacy(connection),
                lambda connection: self._create_duplicate_repository(connection),
            ),
        )
        for legacy_operation, new_operation in operations:
            with self.subTest(operation=legacy_operation.__name__):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_error = self._captured_error(legacy_operation, legacy_connection)
                    new_error = self._captured_error(new_operation, new_connection)
                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_update_matches_legacy_for_existing_and_missing_ids(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_person(legacy_connection, "Casey", "1980-04-03")
            repository = PersonRepository(new_connection)
            person = repository.create("Casey", "1980-04-03")

            legacy_result = update_person_birth_date(legacy_connection, legacy_id, "1981-05-04")
            new_result = repository.update_birth_date(person.id, "1981-05-04")
            update_person_birth_date(legacy_connection, 999, "2000-01-01")
            repository.update_birth_date(999, "2000-01-01")

            self.assertIsNone(legacy_result)
            self.assertIsNone(new_result)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(repository.get(person.id), Person(person.id, "Casey", "1981-05-04"))
            self.assertIsNone(repository.get(999))
            self.assertIsNone(repository.find_by_name("Missing"))

    def test_import_name_resolution_matches_legacy_helper(self):
        for name in (None, "", "  Imported Owner  "):
            with self.subTest(name=name):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_id = _person_id(legacy_connection, name)
                    person = PersonRepository(new_connection).find_or_create(name)
                    self.assertEqual(person.id if person else None, legacy_id)
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

                    repeated_id = _person_id(legacy_connection, name)
                    repeated = PersonRepository(new_connection).find_or_create(name)
                    self.assertEqual(repeated.id if repeated else None, repeated_id)
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    @staticmethod
    def _captured_error(operation, connection: sqlite3.Connection) -> Exception:
        try:
            operation(connection)
        except Exception as error:
            return error
        raise AssertionError("Operation did not raise")

    @staticmethod
    def _create_duplicate_legacy(connection: sqlite3.Connection) -> int:
        create_person(connection, "Casey")
        return create_person(connection, "Casey")

    @staticmethod
    def _create_duplicate_repository(connection: sqlite3.Connection) -> Person:
        repository = PersonRepository(connection)
        repository.create("Casey")
        return repository.create("Casey")
