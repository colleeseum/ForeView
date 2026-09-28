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
from domain.real_estate_projection import RealEstateProjection


class RealEstateProjectionRepository:
    """Persist and retrieve projected real-estate values."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        asset_id: int,
        projection_date: str,
        projected_value: MoneyInput,
        *,
        scenario_id: int | None = None,
        projected_acb: MoneyInput | None = None,
        effective_tax_rate: float | None = None,
        note: str | None = None,
    ) -> RealEstateProjection:
        self._validate(
            projection_date,
            projected_value,
            projected_acb,
            effective_tax_rate,
        )
        cursor = self._connection.execute(
            """INSERT INTO real_estate_projections(
                   asset_id, scenario_id, projection_date, projected_value,
                   projected_value_cents, projected_acb, projected_acb_cents,
                   effective_tax_rate, note
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                scenario_id,
                projection_date,
                storage_decimal(projected_value),
                to_cents(projected_value),
                optional_storage_decimal(projected_acb),
                optional_cents(projected_acb),
                effective_tax_rate,
                note or None,
            ),
        )
        projection = self.get(cursor.lastrowid)
        if projection is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created real-estate projection could not be retrieved")
        return projection

    def get(self, projection_id: int | None) -> RealEstateProjection | None:
        if projection_id is None:
            return None
        row = self._connection.execute(
            f"{self._SELECT} WHERE id = ?",  # noqa: S608 - static query fragment
            (projection_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_asset(self, asset_id: int) -> list[RealEstateProjection]:
        rows = self._connection.execute(
            f"{self._SELECT} WHERE asset_id = ? ORDER BY projection_date, id",  # noqa: S608
            (asset_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    _SELECT = """SELECT id, asset_id, scenario_id, projection_date, projected_value_cents,
                         projected_acb_cents, effective_tax_rate, note
                  FROM real_estate_projections"""

    @staticmethod
    def _validate(
        projection_date: str,
        projected_value: MoneyInput,
        projected_acb: MoneyInput | None,
        effective_tax_rate: float | None,
    ) -> None:
        if as_decimal(projected_value) < 0 or (
            projected_acb is not None and as_decimal(projected_acb) < 0
        ):
            raise ValueError("Projected real-estate values cannot be negative")
        if effective_tax_rate is not None and not 0 <= effective_tax_rate <= 1:
            raise ValueError("Effective tax rate must be between 0 and 1")
        try:
            date.fromisoformat(projection_date)
        except ValueError as error:
            raise ValueError(f"Invalid date: {projection_date}") from error

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> RealEstateProjection:
        projection_id = RealEstateProjectionRepository._required_int(row[0])
        asset_id = RealEstateProjectionRepository._required_int(row[1])
        scenario_id = RealEstateProjectionRepository._optional_int(row[2])
        return RealEstateProjection(
            id=projection_id,
            asset_id=asset_id,
            scenario_id=scenario_id,
            projection_date=str(row[3]),
            projected_value=float(from_cents(row[4])),
            projected_acb=None if row[5] is None else float(from_cents(row[5])),
            effective_tax_rate=RealEstateProjectionRepository._optional_float(row[6]),
            note=str(row[7]) if row[7] is not None else None,
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Real-estate projection identifier must be an integer")
        return value

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        return RealEstateProjectionRepository._required_int(value)

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("Real-estate projection numeric value has an invalid type")
        return float(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        return RealEstateProjectionRepository._required_float(value)
