from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.real_estate_asset_repository import RealEstateAssetRepository
from tests.support import (
    create_real_estate_asset,
    ensure_domain_schema,
    update_real_estate_asset,
)


class RealEstateAssetRepositoryParityTests(unittest.TestCase):
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
                """SELECT id, name, property_type, description, estimated_value,
                          valuation_date, acb, ownership_share, principal_residence,
                          effective_tax_rate
                   FROM real_estate_assets ORDER BY id"""
            ).fetchall()
        ]

    def test_create_matches_legacy_and_returns_immutable_complete_row(self):
        arguments = {
            "name": "  Family land  ",
            "estimated_value": 155000.0,
            "valuation_date": "2026-09-27",
            "property_type": "Property share",
            "description": "Inherited land",
            "acb": 101432.74,
            "ownership_share": 0.5,
            "principal_residence": False,
            "effective_tax_rate": 0.25,
        }
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_real_estate_asset(legacy_connection, **arguments)
            repository = RealEstateAssetRepository(new_connection)
            asset = repository.create(**arguments)

            self.assertEqual(asset.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertEqual(asset.name, "Family land")
            self.assertEqual(asset.acb, 101432.74)
            self.assertEqual(asset.ownership_share, 0.5)
            self.assertFalse(asset.principal_residence)
            self.assertTrue(asset.created_at)
            self.assertTrue(asset.updated_at)
            self.assertEqual(repository.get(asset.id), asset)
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            with self.assertRaises(FrozenInstanceError):
                asset.estimated_value = 0  # type: ignore[misc]

    def test_empty_optional_text_and_defaults_match_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_real_estate_asset(
                legacy_connection,
                "Home",
                1000000,
                "2026-01-01",
                property_type="",
                description="",
                principal_residence=True,
            )
            repository = RealEstateAssetRepository(new_connection)
            asset = repository.create(
                "Home",
                1000000,
                "2026-01-01",
                property_type="",
                description="",
                principal_residence=True,
            )

            self.assertEqual(asset.id, legacy_id)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            self.assertIsNone(asset.property_type)
            self.assertIsNone(asset.description)
            self.assertIsNone(asset.acb)
            self.assertEqual(asset.ownership_share, 1.0)
            self.assertTrue(asset.principal_residence)

    def test_create_validation_errors_match_legacy(self):
        cases = (
            {"name": " ", "estimated_value": 1, "valuation_date": "2026-01-01"},
            {"name": "Land", "estimated_value": -1, "valuation_date": "2026-01-01"},
            {
                "name": "Land",
                "estimated_value": 1,
                "valuation_date": "2026-01-01",
                "acb": -1,
            },
            {
                "name": "Land",
                "estimated_value": 1,
                "valuation_date": "2026-01-01",
                "ownership_share": 0,
            },
            {
                "name": "Land",
                "estimated_value": 1,
                "valuation_date": "2026-01-01",
                "effective_tax_rate": 1.1,
            },
            {"name": "Land", "estimated_value": 1, "valuation_date": "not-a-date"},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self._connection() as legacy_connection, self._connection() as new_connection:
                    legacy_error = self._error(
                        lambda values=arguments: create_real_estate_asset(
                            legacy_connection, **values
                        )
                    )
                    new_error = self._error(
                        lambda values=arguments: RealEstateAssetRepository(new_connection).create(
                            **values
                        )
                    )

                    self.assertEqual(type(new_error), type(legacy_error))
                    self.assertEqual(str(new_error), str(legacy_error))
                    self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))

    def test_update_matches_legacy(self):
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_id = create_real_estate_asset(legacy_connection, "Original", 100, "2026-01-01")
            repository = RealEstateAssetRepository(new_connection)
            asset = repository.create("Original", 100, "2026-01-01")
            arguments = {
                "name": "  Updated  ",
                "estimated_value": 200.0,
                "valuation_date": "2026-02-01",
                "property_type": "Land",
                "description": "Updated description",
                "acb": 50.0,
                "ownership_share": 0.75,
                "principal_residence": True,
                "effective_tax_rate": 0.2,
            }

            legacy_result = update_real_estate_asset(legacy_connection, legacy_id, **arguments)
            new_result = repository.update(asset.id, **arguments)

            self.assertIsNone(legacy_result)
            self.assertIsNone(new_result)
            self.assertEqual(self._rows(new_connection), self._rows(legacy_connection))
            updated = repository.get(asset.id)
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.name, "Updated")
            self.assertEqual(updated.estimated_value, 200.0)

    def test_update_validation_and_missing_id_match_legacy(self):
        invalid = {
            "name": "",
            "estimated_value": 1,
            "valuation_date": "2026-01-01",
        }
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_error = self._error(
                lambda: update_real_estate_asset(legacy_connection, 999, **invalid)
            )
            new_error = self._error(
                lambda: RealEstateAssetRepository(new_connection).update(999, **invalid)
            )
            self.assertEqual(type(new_error), type(legacy_error))
            self.assertEqual(str(new_error), str(legacy_error))

        valid = {**invalid, "name": "Missing"}
        with self._connection() as legacy_connection, self._connection() as new_connection:
            legacy_error = self._error(
                lambda: update_real_estate_asset(legacy_connection, 999, **valid)
            )
            new_error = self._error(
                lambda: RealEstateAssetRepository(new_connection).update(999, **valid)
            )
            self.assertEqual(type(new_error), type(legacy_error))
            self.assertEqual(str(new_error), str(legacy_error))

    def test_list_all_uses_name_then_id_order(self):
        with self._connection() as connection:
            repository = RealEstateAssetRepository(connection)
            repository.create("Zulu", 1, "2026-01-01")
            repository.create("Alpha", 1, "2026-01-01")

            self.assertEqual([asset.name for asset in repository.list_all()], ["Alpha", "Zulu"])

    @staticmethod
    def _error(operation) -> Exception:
        try:
            operation()
        except Exception as error:
            return error
        raise AssertionError("Operation did not raise")
