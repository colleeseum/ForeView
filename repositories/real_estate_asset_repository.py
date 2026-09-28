from __future__ import annotations

import sqlite3
from datetime import date

from domain.money import (
    MoneyInput,
    as_decimal,
    from_cents,
    optional_cents,
    optional_storage_decimal,
    storage_decimal,
    to_cents,
)
from domain.real_estate_asset import RealEstateAsset


class RealEstateAssetRepository:
    """Persist and retrieve factual real-estate asset rows."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        name: str,
        estimated_value: MoneyInput,
        valuation_date: str,
        *,
        property_type: str | None = None,
        description: str | None = None,
        acb: MoneyInput | None = None,
        ownership_share: float = 1.0,
        principal_residence: bool = False,
        effective_tax_rate: float | None = None,
    ) -> RealEstateAsset:
        clean_name = self._validate(
            name,
            estimated_value,
            valuation_date,
            acb,
            ownership_share,
            effective_tax_rate,
        )
        cursor = self._connection.execute(
            """INSERT INTO real_estate_assets(
                   name, property_type, description, estimated_value, valuation_date, acb,
                   estimated_value_cents, acb_cents, ownership_share,
                   principal_residence, effective_tax_rate
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                clean_name,
                property_type or None,
                description or None,
                storage_decimal(estimated_value),
                valuation_date,
                optional_storage_decimal(acb),
                to_cents(estimated_value),
                optional_cents(acb),
                ownership_share,
                int(principal_residence),
                effective_tax_rate,
            ),
        )
        asset = self.get(cursor.lastrowid)
        if asset is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created real-estate asset could not be retrieved")
        return asset

    def update(
        self,
        asset_id: int,
        name: str,
        estimated_value: MoneyInput,
        valuation_date: str,
        *,
        property_type: str | None = None,
        description: str | None = None,
        acb: MoneyInput | None = None,
        ownership_share: float = 1.0,
        principal_residence: bool = False,
        effective_tax_rate: float | None = None,
    ) -> None:
        clean_name = self._validate(
            name,
            estimated_value,
            valuation_date,
            acb,
            ownership_share,
            effective_tax_rate,
        )
        cursor = self._connection.execute(
            """UPDATE real_estate_assets
               SET name = ?, property_type = ?, description = ?, estimated_value = ?,
                   estimated_value_cents = ?, valuation_date = ?, acb = ?, acb_cents = ?,
                   ownership_share = ?, principal_residence = ?, effective_tax_rate = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                clean_name,
                property_type or None,
                description or None,
                storage_decimal(estimated_value),
                to_cents(estimated_value),
                valuation_date,
                optional_storage_decimal(acb),
                optional_cents(acb),
                ownership_share,
                int(principal_residence),
                effective_tax_rate,
                asset_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Real-estate asset not found")

    def get(self, asset_id: int | None) -> RealEstateAsset | None:
        if asset_id is None:
            return None
        row = self._connection.execute(
            f"{self._SELECT} WHERE id = ?",  # noqa: S608 - static query fragment
            (asset_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_all(self) -> list[RealEstateAsset]:
        rows = self._connection.execute(f"{self._SELECT} ORDER BY name, id").fetchall()  # noqa: S608
        return [self._from_row(row) for row in rows]

    _SELECT = """SELECT id, name, property_type, description, estimated_value_cents,
                         valuation_date, acb_cents, ownership_share, principal_residence,
                         effective_tax_rate, created_at, updated_at
                  FROM real_estate_assets"""

    @staticmethod
    def _validate(
        name: str,
        estimated_value: MoneyInput,
        valuation_date: str,
        acb: MoneyInput | None,
        ownership_share: float,
        effective_tax_rate: float | None,
    ) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Real-estate asset name is required")
        if as_decimal(estimated_value) < 0 or (acb is not None and as_decimal(acb) < 0):
            raise ValueError("Real-estate values cannot be negative")
        if not 0 < ownership_share <= 1:
            raise ValueError("Ownership share must be between 0 and 1")
        if effective_tax_rate is not None and not 0 <= effective_tax_rate <= 1:
            raise ValueError("Effective tax rate must be between 0 and 1")
        try:
            date.fromisoformat(valuation_date)
        except ValueError as error:
            raise ValueError(f"Invalid date: {valuation_date}") from error
        return clean_name

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> RealEstateAsset:
        asset_id = row[0]
        if not isinstance(asset_id, int):
            raise TypeError("Real-estate asset id must be an integer")
        return RealEstateAsset(
            id=asset_id,
            name=str(row[1]),
            property_type=str(row[2]) if row[2] is not None else None,
            description=str(row[3]) if row[3] is not None else None,
            estimated_value=float(from_cents(row[4])),
            valuation_date=str(row[5]),
            acb=None if row[6] is None else float(from_cents(row[6])),
            ownership_share=RealEstateAssetRepository._required_float(row[7]),
            principal_residence=bool(row[8]),
            effective_tax_rate=RealEstateAssetRepository._optional_float(row[9]),
            created_at=str(row[10]),
            updated_at=str(row[11]),
        )

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("Real-estate numeric value has an invalid type")
        return float(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        return RealEstateAssetRepository._required_float(value)
