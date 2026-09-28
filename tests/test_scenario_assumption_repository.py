from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.scenario_assumption_repository import ScenarioAssumptionRepository
from tests.support import create_scenario, ensure_domain_schema, set_scenario_assumption


class ScenarioAssumptionRepositoryParityTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _scenario(connection: sqlite3.Connection) -> int:
        return create_scenario(connection, "Baseline", "2026-01-01")

    @staticmethod
    def _rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
        return [
            tuple(row)
            for row in connection.execute(
                """SELECT scenario_id, key, value, unit
                   FROM scenario_assumptions ORDER BY scenario_id, key"""
            ).fetchall()
        ]

    def test_set_matches_legacy_and_returns_immutable_object(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_scenario = self._scenario(legacy_connection)
            new_scenario = self._scenario(new_connection)

            legacy_result = set_scenario_assumption(
                legacy_connection,
                legacy_scenario,
                "general_growth_rate",
                "0.04",
                "annual_rate",
            )
            repository = ScenarioAssumptionRepository(new_connection)
            new_result = repository.set(
                new_scenario,
                "general_growth_rate",
                "0.04",
                "annual_rate",
            )

            self.assertIsNone(legacy_result)
            self.assertIsNone(new_result)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            assumption = repository.get(new_scenario, "general_growth_rate")
            self.assertIsNotNone(assumption)
            assert assumption is not None
            self.assertEqual(assumption.value, "0.04")
            self.assertEqual(assumption.unit, "annual_rate")
            with self.assertRaises(FrozenInstanceError):
                assumption.value = "0.05"  # type: ignore[misc]

    def test_replace_same_composite_key_matches_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_scenario = self._scenario(legacy_connection)
            new_scenario = self._scenario(new_connection)
            repository = ScenarioAssumptionRepository(new_connection)

            set_scenario_assumption(
                legacy_connection, legacy_scenario, "inflation", "0.02", "annual_rate"
            )
            repository.set(new_scenario, "inflation", "0.02", "annual_rate")
            set_scenario_assumption(legacy_connection, legacy_scenario, "inflation", "0.025", None)
            repository.set(new_scenario, "inflation", "0.025", None)

            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            assumptions = repository.list_for_scenario(new_scenario)
            self.assertEqual(len(assumptions), 1)
            self.assertEqual(assumptions[0].value, "0.025")
            self.assertIsNone(assumptions[0].unit)

    def test_multiple_keys_are_ordered_and_isolated_by_scenario(self):
        with self._connection() as connection:
            first = self._scenario(connection)
            second = create_scenario(connection, "Alternative", "2026-01-01")
            repository = ScenarioAssumptionRepository(connection)
            repository.set(first, "wage_growth", "0.03")
            repository.set(first, "inflation", "0.02")
            repository.set(second, "inflation", "0.01")

            assumptions = repository.list_for_scenario(first)

            self.assertEqual([item.key for item in assumptions], ["inflation", "wage_growth"])
            self.assertEqual([item.value for item in assumptions], ["0.02", "0.03"])
            self.assertIsNone(repository.get(first, "missing"))
            self.assertEqual(repository.get(second, "inflation").value, "0.01")  # type: ignore[union-attr]

    def test_blank_fields_and_missing_parent_behavior_match_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_result = set_scenario_assumption(legacy_connection, 999, "", "", "")
            new_result = ScenarioAssumptionRepository(new_connection).set(999, "", "", "")

            self.assertIsNone(legacy_result)
            self.assertIsNone(new_result)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
