# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.scenario_repository import ScenarioRepository
from tests.support import create_scenario, ensure_domain_schema


class ScenarioRepositoryParityTests(unittest.TestCase):
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
                "SELECT id, name, baseline_date, description FROM scenarios ORDER BY id"
            ).fetchall()
        ]

    def test_create_matches_legacy_and_returns_immutable_object(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_scenario(
                legacy_connection,
                "  Retirement baseline  ",
                "2026-09-27",
                "Current assumptions",
            )
            repository = ScenarioRepository(new_connection)
            scenario = repository.create(
                "  Retirement baseline  ",
                "2026-09-27",
                "Current assumptions",
            )

            self.assertEqual(scenario.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(scenario.name, "Retirement baseline")
            self.assertEqual(scenario.baseline_date, "2026-09-27")
            self.assertEqual(scenario.description, "Current assumptions")
            self.assertEqual(repository.get(scenario.id), scenario)
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            with self.assertRaises(FrozenInstanceError):
                scenario.name = "Changed"  # type: ignore[misc]

    def test_multiple_scenarios_and_default_description_match_legacy(self):
        definitions = (
            ("Baseline", "2026-01-01"),
            ("Conservative", "2027-01-01"),
        )
        with self._connection() as legacy_connection, self._connection() as new_connection:
            repository = ScenarioRepository(new_connection)
            for name, baseline_date in definitions:
                create_scenario(legacy_connection, name, baseline_date)
                repository.create(name, baseline_date)

            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            scenarios = repository.list_all()
            self.assertEqual(
                [scenario.name for scenario in scenarios], ["Baseline", "Conservative"]
            )
            self.assertTrue(all(scenario.description is None for scenario in scenarios))

    def test_duplicate_name_integrity_error_matches_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            create_scenario(legacy_connection, "Duplicate", "2026-01-01")
            repository = ScenarioRepository(new_connection)
            repository.create("Duplicate", "2026-01-01")

            legacy_error = self._error(
                lambda: create_scenario(legacy_connection, " Duplicate ", "2027-01-01")
            )
            new_error = self._error(lambda: repository.create(" Duplicate ", "2027-01-01"))

            self.assertEqual(type(new_error), type(legacy_error))
            self.assertEqual(str(new_error), str(legacy_error))
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_blank_name_and_unparsed_date_behavior_matches_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_scenario(legacy_connection, "   ", "not-a-date")
            scenario = ScenarioRepository(new_connection).create("   ", "not-a-date")

            self.assertEqual(scenario.id, legacy_id)
            self.assertEqual(scenario.name, "")
            self.assertEqual(scenario.baseline_date, "not-a-date")
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    @staticmethod
    def _error(operation) -> Exception:
        try:
            operation()
        except Exception as error:
            return error
        raise AssertionError("Operation did not raise")
