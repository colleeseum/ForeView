# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from typing import Any

from flask import jsonify, request

from domain.money import as_decimal
from repositories.real_estate_asset_repository import RealEstateAssetRepository
from repositories.real_estate_ownership_repository import RealEstateOwnershipRepository
from repositories.real_estate_projection_repository import RealEstateProjectionRepository
from services.real_estate_summary_query import RealEstateSummaryQuery
from web.dependencies import dependency
from web.model_blueprint import blueprint
from web.route_values import payload_bool


@blueprint.get("/api/model/real-estate")
def model_real_estate():
    with dependency("connect")() as connection:
        return jsonify({"assets": RealEstateSummaryQuery(connection).execute()})


def _owners(payload: Any) -> list[tuple[int, float]]:
    return [(int(item["person_id"]), float(item["share"])) for item in payload.get("owners", [])]


@blueprint.post("/api/model/real-estate")
def add_real_estate_route():
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            asset = RealEstateAssetRepository(connection).create(
                str(payload["name"]),
                as_decimal(payload["estimated_value"]),
                str(payload["valuation_date"]),
                property_type=payload.get("property_type"),
                description=payload.get("description"),
                acb=as_decimal(payload["acb"]) if payload.get("acb") not in (None, "") else None,
                ownership_share=float(payload.get("ownership_share", 1)),
                principal_residence=payload_bool(payload.get("principal_residence", False)),
                effective_tax_rate=float(payload["effective_tax_rate"])
                if payload.get("effective_tax_rate") not in (None, "")
                else None,
            )
            RealEstateOwnershipRepository(connection).replace(asset.id, _owners(payload))
        return jsonify({"id": asset.id}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put("/api/model/real-estate/<int:asset_id>")
def update_real_estate_route(asset_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            RealEstateAssetRepository(connection).update(
                asset_id,
                str(payload["name"]),
                as_decimal(payload["estimated_value"]),
                str(payload["valuation_date"]),
                property_type=payload.get("property_type"),
                description=payload.get("description"),
                acb=as_decimal(payload["acb"]) if payload.get("acb") not in (None, "") else None,
                ownership_share=float(payload.get("ownership_share", 1)),
                principal_residence=payload_bool(payload.get("principal_residence", False)),
                effective_tax_rate=float(payload["effective_tax_rate"])
                if payload.get("effective_tax_rate") not in (None, "")
                else None,
            )
            RealEstateOwnershipRepository(connection).replace(asset_id, _owners(payload))
        return jsonify({"updated": True})
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/model/real-estate/<int:asset_id>/projections")
def add_real_estate_projection_route(asset_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            projection = RealEstateProjectionRepository(connection).create(
                asset_id,
                str(payload["projection_date"]),
                as_decimal(payload["projected_value"]),
                scenario_id=int(payload["scenario_id"])
                if payload.get("scenario_id") not in (None, "")
                else None,
                projected_acb=as_decimal(payload["projected_acb"])
                if payload.get("projected_acb") not in (None, "")
                else None,
                effective_tax_rate=float(payload["effective_tax_rate"])
                if payload.get("effective_tax_rate") not in (None, "")
                else None,
                note=payload.get("note"),
            )
        return jsonify({"id": projection.id}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400
