from __future__ import annotations

import sqlite3

from domain.real_estate_ownership import RealEstateOwnership


class RealEstateOwnershipRepository:
    """Replace and retrieve ownership shares for a real-estate asset."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace(self, asset_id: int, owners: list[tuple[int, float]]) -> None:
        self._validate(owners)
        self._connection.execute(
            "DELETE FROM real_estate_owners WHERE asset_id = ?",
            (asset_id,),
        )
        self._connection.executemany(
            """INSERT INTO real_estate_owners(asset_id, person_id, ownership_share)
               VALUES (?, ?, ?)""",
            [(asset_id, person_id, share) for person_id, share in owners],
        )

    def owners_with_names(self, asset_id: int) -> list[sqlite3.Row]:
        """Owner name, person id, and share for an asset, ordered by name."""
        return self._connection.execute(
            """SELECT p.name, reo.person_id, reo.ownership_share
               FROM real_estate_owners reo JOIN people p ON p.id = reo.person_id
               WHERE reo.asset_id = ? ORDER BY p.name""",
            (asset_id,),
        ).fetchall()

    def list_for_asset(self, asset_id: int) -> list[RealEstateOwnership]:
        rows = self._connection.execute(
            """SELECT asset_id, person_id, ownership_share
               FROM real_estate_owners WHERE asset_id = ? ORDER BY person_id""",
            (asset_id,),
        ).fetchall()
        return [
            RealEstateOwnership(
                asset_id=self._required_int(row[0]),
                person_id=self._required_int(row[1]),
                share=self._required_float(row[2]),
            )
            for row in rows
        ]

    @staticmethod
    def _validate(owners: list[tuple[int, float]]) -> None:
        if not owners:
            raise ValueError("At least one real-estate owner is required")
        total = sum(share for _, share in owners)
        if abs(total - 1.0) > 0.000001:
            raise ValueError("Real-estate ownership shares must total 100%")
        if any(share <= 0 or share > 1 for _, share in owners):
            raise ValueError("Ownership shares must be between 0% and 100%")

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Real-estate ownership identifier must be an integer")
        return value

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("Real-estate ownership share has an invalid type")
        return float(value)
