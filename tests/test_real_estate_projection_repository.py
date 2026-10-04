# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.real_estate_projection_repository import RealEstateProjectionRepository
from tests.support import (
    add_real_estate_projection,
    create_real_estate_asset,
    create_scenario,
    ensure_domain_schema,
)


class RealEstateProjectionRepositoryParityTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _fixture(connection: sqlite3.Connection) -> tuple[int, int]:
        asset = create_real_estate_asset(connection, "Land", 100000, "2026-01-01")
        scenario = create_scenario(connection, "Baseline", "2026-01-01")
        return asset, scenario

    @staticmethod
    def _rows(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
        return [
            tuple(row)
            for row in connection.execute(
                """SELECT id, asset_id, scenario_id, projection_date, projected_value,
                          projected_acb, effective_tax_rate, note
                   FROM real_estate_projections ORDER BY id"""
            ).fetchall()
        ]

    def test_create_matches_legacy_and_returns_immutable_complete_row(self):
        arguments = {
            "projection_date": "2030-01-01",
            "projected_value": 175000.0,
            "projected_acb": 100000.0,
            "effective_tax_rate": 0.3,
            "note": "Baseline projection",
        }
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_asset, legacy_scenario = self._fixture(legacy_connection)
            new_asset, new_scenario = self._fixture(new_connection)

            legacy_id = add_real_estate_projection(
                legacy_connection,
                legacy_asset,
                scenario_id=legacy_scenario,
                **arguments,
            )
            repository = RealEstateProjectionRepository(new_connection)
            projection = repository.create(
                new_asset,
                scenario_id=new_scenario,
                **arguments,
            )

            self.assertEqual(projection.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(projection.projected_value, 175000.0)
            self.assertEqual(projection.projected_acb, 100000.0)
            self.assertEqual(projection.effective_tax_rate, 0.3)
            self.assertEqual(projection.note, "Baseline projection")
            self.assertEqual(repository.get(projection.id), projection)
            self.assertEqual(repository.list_for_asset(new_asset), [projection])
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            with self.assertRaises(FrozenInstanceError):
                projection.projected_value = 0  # type: ignore[misc]

    def test_optional_fields_and_empty_note_match_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_asset, _ = self._fixture(legacy_connection)
            new_asset, _ = self._fixture(new_connection)
            legacy_id = add_real_estate_projection(
                legacy_connection,
                legacy_asset,
                "2030-01-01",
                150000,
                note="",
            )
            projection = RealEstateProjectionRepository(new_connection).create(
                new_asset,
                "2030-01-01",
                150000,
                note="",
            )

            self.assertEqual(projection.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertIsNone(projection.scenario_id)
            self.assertIsNone(projection.projected_acb)
            self.assertIsNone(projection.effective_tax_rate)
            self.assertIsNone(projection.note)

    def test_validation_errors_match_legacy(self):
        cases = (
            {"projection_date": "2030-01-01", "projected_value": -1},
            {
                "projection_date": "2030-01-01",
                "projected_value": 1,
                "projected_acb": -1,
            },
            {
                "projection_date": "2030-01-01",
                "projected_value": 1,
                "effective_tax_rate": -0.1,
            },
            {"projection_date": "invalid", "projected_value": 1},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_asset, _ = self._fixture(legacy_connection)
                    new_asset, _ = self._fixture(new_connection)
                    legacy_error = self._error(
                        lambda values=arguments, asset=legacy_asset: add_real_estate_projection(
                            legacy_connection,
                            asset,
                            **values,
                        )
                    )
                    new_error = self._error(
                        lambda values=arguments, asset=new_asset: RealEstateProjectionRepository(
                            new_connection
                        ).create(
                            asset,
                            **values,
                        )
                    )

                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_unique_scenario_date_behavior_matches_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_asset, legacy_scenario = self._fixture(legacy_connection)
            new_asset, new_scenario = self._fixture(new_connection)
            add_real_estate_projection(
                legacy_connection,
                legacy_asset,
                "2030-01-01",
                100,
                scenario_id=legacy_scenario,
            )
            repository = RealEstateProjectionRepository(new_connection)
            repository.create(
                new_asset,
                "2030-01-01",
                100,
                scenario_id=new_scenario,
            )

            legacy_error = self._error(
                lambda: add_real_estate_projection(
                    legacy_connection,
                    legacy_asset,
                    "2030-01-01",
                    200,
                    scenario_id=legacy_scenario,
                )
            )
            new_error = self._error(
                lambda: repository.create(
                    new_asset,
                    "2030-01-01",
                    200,
                    scenario_id=new_scenario,
                )
            )

            self.assertEqual(type(new_error), type(legacy_error))
            self.assertEqual(str(new_error), str(legacy_error))
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_null_scenario_allows_same_asset_and_date_like_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_asset, _ = self._fixture(legacy_connection)
            new_asset, _ = self._fixture(new_connection)
            repository = RealEstateProjectionRepository(new_connection)
            for value in (100.0, 200.0):
                add_real_estate_projection(
                    legacy_connection,
                    legacy_asset,
                    "2030-01-01",
                    value,
                )
                repository.create(new_asset, "2030-01-01", value)

            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(len(repository.list_for_asset(new_asset)), 2)

    @staticmethod
    def _error(operation) -> Exception:
        try:
            operation()
        except Exception as error:
            return error
        raise AssertionError("Operation did not raise")
