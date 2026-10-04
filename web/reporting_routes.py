# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from flask import jsonify, request

from repositories.scenario_assumption_repository import ScenarioAssumptionRepository
from repositories.scenario_repository import ScenarioRepository
from services.reporting_query import ReportingQuery
from web.dependencies import dependency
from web.model_blueprint import blueprint


@blueprint.get("/api/model/import-history")
def model_import_history():
    account_id = request.args.get("account_id", type=int)
    account_type = request.args.get("account_type")
    with dependency("connect")() as connection:
        return jsonify(
            {"imports": ReportingQuery(connection).import_history(account_id, account_type)}
        )


@blueprint.get("/api/model/holdings")
def model_holdings():
    account_id = request.args.get("account_id", type=int)
    account_type = request.args.get("account_type")
    with dependency("connect")() as connection:
        return jsonify({"holdings": ReportingQuery(connection).holdings(account_id, account_type)})


@blueprint.post("/api/model/scenarios")
def add_scenario_route():
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            scenario = ScenarioRepository(connection).create(
                str(payload["name"]), str(payload["baseline_date"])
            )
            ScenarioAssumptionRepository(connection).set(
                scenario.id,
                "general_growth_rate",
                str(payload.get("growth_rate", "0.04")),
                "annual_rate",
            )
        return jsonify({"id": scenario.id}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.get("/api/model/annual-summary")
def model_annual_summary():
    with dependency("connect")() as connection:
        return jsonify({"summary": ReportingQuery(connection).annual_summary()})
