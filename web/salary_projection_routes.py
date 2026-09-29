from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.employment_baseline import EmploymentBaseline
from domain.employment_projection_override import EmploymentProjectionOverride
from domain.employment_projection_settings import EmploymentProjectionSettings
from domain.money import as_decimal
from domain.projected_employment_year import ProjectedEmploymentYear
from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.employment_baseline_repository import EmploymentBaselineRepository
from repositories.employment_projection_override_repository import (
    EmploymentProjectionOverrideRepository,
)
from repositories.employment_projection_settings_repository import (
    EmploymentProjectionSettingsRepository,
)
from repositories.person_repository import PersonRepository
from repositories.scenario_repository import ScenarioRepository
from services.salary_projection_service import SalaryProjectionService
from web.dependencies import dependency

blueprint = Blueprint("salary_projection", __name__)


@blueprint.get("/salary-projection")
def salary_projection_page():
    return render_template("salary_projection.html")


@blueprint.get("/api/salary-projection")
def salary_projection_data():
    start_year = request.args.get("start_year", type=int) or date.today().year
    end_year = request.args.get("end_year", type=int) or start_year + 9
    if end_year < start_year or end_year - start_year > 100:
        return jsonify({"error": "Projection range must be between 1 and 101 years"}), 400
    with dependency("connect")() as connection:
        people = PersonRepository(connection).list_all()
        scenarios = ScenarioRepository(connection).list_all()
        requested_scenario = request.args.get("scenario_id", type=int)
        scenario_id = requested_scenario or (scenarios[0].id if scenarios else None)
        result_people: list[dict[str, Any]] = []
        for person in people:
            baseline = EmploymentBaselineRepository(connection).get_effective(
                person.id, f"{start_year}-12-31"
            )
            settings = (
                EmploymentProjectionSettingsRepository(connection).get(scenario_id, person.id)
                if scenario_id is not None
                else None
            )
            actuals = AnnualEmploymentActualRepository(connection).list_for_person(person.id)
            latest_actual = max(actuals, key=lambda item: item.tax_year) if actuals else None
            overrides = (
                EmploymentProjectionOverrideRepository(connection).list_for_person(
                    scenario_id, person.id
                )
                if scenario_id is not None
                else []
            )
            rows: tuple[ProjectedEmploymentYear, ...] = ()
            error = None
            if scenario_id is not None and baseline is not None and settings is not None:
                try:
                    rows = SalaryProjectionService(
                        connection,
                        current_app.extensions["finance_public_rules_path"](),
                    ).project_person(scenario_id, person.id, start_year, end_year)
                except ValueError as caught:
                    error = str(caught)
            result_people.append(
                {
                    "id": person.id,
                    "name": person.name,
                    "birth_date": person.birth_date,
                    "baseline": _baseline_json(baseline),
                    "settings": _settings_json(settings),
                    "salary_anchor": _actual_json(latest_actual) if latest_actual else None,
                    "actuals": [_actual_json(latest_actual)] if latest_actual else [],
                    "overrides": [_override_json(item) for item in overrides],
                    "projection": [_projection_json(item) for item in rows],
                    "error": error,
                }
            )
        household = _household_projection(result_people)
        return jsonify(
            {
                "scenarios": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "baseline_date": item.baseline_date,
                        "description": item.description,
                    }
                    for item in scenarios
                ],
                "selected_scenario_id": scenario_id,
                "start_year": start_year,
                "end_year": end_year,
                "people": result_people,
                "household": household,
            }
        )


@blueprint.put("/api/salary-projection/people/<int:person_id>/baseline")
def save_employment_baseline(person_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            baseline = EmploymentBaselineRepository(connection).upsert(
                person_id,
                str(payload["effective_date"]),
                as_decimal(payload["annual_salary"]),
                str(payload["province_of_employment"]),
                str(payload["payroll_plan"]),
                str(payload.get("source") or "manual"),
            )
        return jsonify(_baseline_json(baseline))
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put("/api/salary-projection/scenarios/<int:scenario_id>/people/<int:person_id>/settings")
def save_employment_settings(scenario_id: int, person_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            repository = EmploymentProjectionSettingsRepository(connection)
            current = repository.get(scenario_id, person_id)
            settings = repository.upsert(
                scenario_id,
                person_id,
                default_raise=as_decimal(payload.get("default_raise", 0)),
                retirement_date=payload.get("retirement_date") or None,
                recurring_rrsp_contribution=as_decimal(
                    payload.get(
                        "recurring_rrsp_contribution",
                        current.recurring_rrsp_contribution if current else 0,
                    )
                ),
                recurring_rrsp_deduction=as_decimal(
                    payload.get(
                        "recurring_rrsp_deduction",
                        current.recurring_rrsp_deduction if current else 0,
                    )
                ),
                recurring_other_income=as_decimal(
                    payload.get(
                        "recurring_other_income",
                        current.recurring_other_income if current else 0,
                    )
                ),
            )
        return jsonify(_settings_json(settings))
    except (TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put(
    "/api/salary-projection/scenarios/<int:scenario_id>/people/<int:person_id>/years/<int:year>"
)
def save_employment_override(scenario_id: int, person_id: int, year: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            override = EmploymentProjectionOverrideRepository(connection).upsert(
                scenario_id,
                person_id,
                year,
                salary=_optional_decimal(payload, "salary"),
                raise_rate=_optional_decimal(payload, "raise_rate"),
                rrsp_contribution=_optional_decimal(payload, "rrsp_contribution"),
                rrsp_deduction=_optional_decimal(payload, "rrsp_deduction"),
                other_income=_optional_decimal(payload, "other_income"),
            )
        return jsonify(
            {
                "year": override.projection_year,
                "saved": True,
            }
        )
    except (TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put(
    "/api/salary-projection/scenarios/<int:scenario_id>/people/<int:person_id>/overrides"
)
def save_employment_overrides(scenario_id: int, person_id: int):
    payload = request.get_json(silent=True) or {}
    overrides = payload.get("overrides")
    if not isinstance(overrides, list):
        return jsonify({"error": "Overrides must be a list"}), 400
    try:
        saved_years = []
        with dependency("connect")() as connection:
            repository = EmploymentProjectionOverrideRepository(connection)
            for item in overrides:
                if not isinstance(item, dict):
                    raise ValueError("Each override must be an object")
                year = int(item["year"])
                repository.upsert(
                    scenario_id,
                    person_id,
                    year,
                    salary=_optional_decimal(item, "salary"),
                    raise_rate=_optional_decimal(item, "raise_rate"),
                    rrsp_contribution=_optional_decimal(item, "rrsp_contribution"),
                    rrsp_deduction=_optional_decimal(item, "rrsp_deduction"),
                    other_income=_optional_decimal(item, "other_income"),
                )
                saved_years.append(year)
        return jsonify({"saved_years": saved_years})
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.delete(
    "/api/salary-projection/scenarios/<int:scenario_id>/people/<int:person_id>/years/<int:year>"
)
def delete_employment_override(scenario_id: int, person_id: int, year: int):
    with dependency("connect")() as connection:
        EmploymentProjectionOverrideRepository(connection).delete(scenario_id, person_id, year)
    return jsonify({"deleted": True})


@blueprint.put("/api/salary-projection/people/<int:person_id>/actuals/<int:tax_year>")
def save_employment_actual(person_id: int, tax_year: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            actual = AnnualEmploymentActualRepository(connection).upsert(
                person_id,
                tax_year,
                as_decimal(payload["salary_income"]),
                province_of_employment=str(payload.get("province_of_employment") or ""),
                bonus=as_decimal(payload.get("bonus", 0)),
                other_income=as_decimal(payload.get("other_income", 0)),
                rrsp_contribution=as_decimal(payload.get("rrsp_contribution", 0)),
                rrsp_deduction=as_decimal(payload.get("rrsp_deduction", 0)),
                cpp_qpp=as_decimal(payload.get("cpp_qpp", 0)),
                ei=as_decimal(payload.get("ei", 0)),
                qpip=as_decimal(payload.get("qpip", 0)),
                federal_tax=as_decimal(payload.get("federal_tax", 0)),
                provincial_tax=as_decimal(payload.get("quebec_tax", 0)),
                source=str(payload.get("source") or "manual"),
            )
        return jsonify(_actual_json(actual))
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


def _optional_decimal(payload: dict[str, object], key: str) -> Decimal | None:
    value = payload.get(key)
    return None if value in (None, "") else as_decimal(str(value))


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _baseline_json(item: EmploymentBaseline | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "effective_date": item.effective_date,
        "annual_salary": _money(item.annual_salary),
        "province_of_employment": item.province_of_employment,
        "payroll_plan": item.payroll_plan,
        "source": item.source,
    }


def _settings_json(item: EmploymentProjectionSettings | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "default_raise": str(item.default_raise),
        "retirement_date": item.retirement_date,
        "recurring_rrsp_contribution": _money(item.recurring_rrsp_contribution),
        "recurring_rrsp_deduction": _money(item.recurring_rrsp_deduction),
        "recurring_other_income": _money(item.recurring_other_income),
    }


def _actual_json(item: AnnualEmploymentActual) -> dict[str, object]:
    return {
        "year": item.tax_year,
        "province_of_employment": item.province_of_employment,
        "payroll_plan": item.payroll_plan,
        "salary_income": _money(item.salary_income),
        "bonus": _money(item.bonus),
        "annual_salary_rate": _money(item.salary_rate),
        "other_income": _money(item.other_income),
        "gross_income": _money(item.gross_income),
        "rrsp_contribution": _money(item.rrsp_contribution),
        "rrsp_deduction": _money(item.rrsp_deduction),
        "cpp_qpp": _money(item.cpp_qpp),
        "ei": _money(item.ei),
        "qpip": _money(item.qpip),
        "federal_tax": _money(item.federal_tax),
        "quebec_tax": _money(item.provincial_tax),
        "disposable_income": _money(item.disposable_income),
        "source": item.source,
        "actual": True,
    }


def _projection_json(item: ProjectedEmploymentYear) -> dict[str, object]:
    return {
        "year": item.year,
        "age": item.age,
        "annual_salary_rate": _money(item.annual_salary_rate),
        "raise_rate": None if item.raise_rate is None else str(item.raise_rate),
        "employment_fraction": str(item.employment_fraction),
        "salary_income": _money(item.salary_income),
        "other_income": _money(item.other_income),
        "gross_income": _money(item.gross_income),
        "rrsp_contribution": _money(item.rrsp_contribution),
        "rrsp_deduction": _money(item.rrsp_deduction),
        "cpp_qpp": _money(item.cpp_qpp),
        "ei": _money(item.ei),
        "qpip": _money(item.qpip),
        "federal_tax": _money(item.federal_tax),
        "quebec_tax": _money(item.quebec_tax),
        "net_income_after_tax": _money(item.net_income_after_tax),
        "disposable_income": _money(item.disposable_income),
        "rule_year": item.rule_year,
        "rules_held_constant": item.rules_held_constant,
        "actual": False,
    }


def _override_json(item: EmploymentProjectionOverride) -> dict[str, object]:
    return {
        "year": item.projection_year,
        "salary": None if item.salary is None else _money(item.salary),
        "raise_rate": None if item.raise_rate is None else str(item.raise_rate),
        "rrsp_contribution": (
            None if item.rrsp_contribution is None else _money(item.rrsp_contribution)
        ),
        "rrsp_deduction": None if item.rrsp_deduction is None else _money(item.rrsp_deduction),
        "other_income": None if item.other_income is None else _money(item.other_income),
    }


def _household_projection(people: list[dict[str, Any]]) -> list[dict[str, object]]:
    totals: dict[int, dict[str, Decimal]] = {}
    fields = (
        "salary_income",
        "other_income",
        "gross_income",
        "rrsp_contribution",
        "rrsp_deduction",
        "cpp_qpp",
        "ei",
        "qpip",
        "federal_tax",
        "quebec_tax",
        "net_income_after_tax",
        "disposable_income",
    )
    for person in people:
        projection = person.get("projection")
        if not isinstance(projection, list):
            continue
        for row in projection:
            if not isinstance(row, dict):
                continue
            year = int(row["year"])
            year_totals = totals.setdefault(year, {field: Decimal("0") for field in fields})
            for field in fields:
                year_totals[field] += Decimal(str(row[field]))
    return [
        {"year": year, **{field: _money(value) for field, value in values.items()}}
        for year, values in sorted(totals.items())
    ]
