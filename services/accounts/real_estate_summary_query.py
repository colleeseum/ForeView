# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Read real-estate facts, ownership, and stored projections."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from decimal import Decimal

from domain.money import as_decimal
from repositories.real_estate_asset_repository import RealEstateAssetRepository
from repositories.real_estate_ownership_repository import RealEstateOwnershipRepository
from repositories.real_estate_projection_repository import RealEstateProjectionRepository


class RealEstateSummaryQuery:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._assets = RealEstateAssetRepository(connection)
        self._projections = RealEstateProjectionRepository(connection)
        self._owners = RealEstateOwnershipRepository(connection)

    def execute(self) -> list[dict[str, object]]:
        result = []
        for asset in self._assets.list_all():
            item = asdict(asset)
            owner_rows = self._owners.owners_with_names(asset.id)
            item["owners"] = [
                {
                    "person_id": row["person_id"],
                    "name": row["name"],
                    "share": row["ownership_share"],
                }
                for row in owner_rows
            ]
            item["owner_details"] = ",".join(
                f"{row['person_id']}:{row['ownership_share']}" for row in owner_rows
            )
            item.update(
                self._tax_values(
                    asset.estimated_value,
                    asset.acb,
                    asset.principal_residence,
                    asset.effective_tax_rate,
                )
            )
            item["projections"] = [
                asdict(projection) for projection in self._projections.list_for_asset(asset.id)
            ]
            result.append(item)
        return result

    @staticmethod
    def _tax_values(
        estimated_value: float,
        acb: float | None,
        principal_residence: bool,
        effective_tax_rate: float | None,
    ) -> dict[str, float | None]:
        if acb is None:
            return {
                "estimated_gain": None,
                "estimated_tax": 0.0 if principal_residence else None,
                "estimated_net_value": estimated_value if principal_residence else None,
            }
        value = as_decimal(estimated_value)
        cost = as_decimal(acb)
        gain = max(as_decimal(0), value - cost)
        tax = (
            as_decimal(0)
            if principal_residence
            else (
                as_decimal(gain * Decimal(str(effective_tax_rate)))
                if effective_tax_rate is not None
                else None
            )
        )
        return {
            "estimated_gain": float(gain),
            "estimated_tax": float(tax) if tax is not None else None,
            "estimated_net_value": float(value - tax) if tax is not None else None,
        }
