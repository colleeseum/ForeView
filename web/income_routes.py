from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.money import as_decimal
from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.person_repository import PersonRepository
from services.ufile_tax_return_parser import UFileTaxReturnParser
from web.dependencies import dependency

blueprint = Blueprint("income", __name__)


@blueprint.get("/api/income")
def income_record():
    year = request.args.get("year", type=int)
    person_id = request.args.get("person_id", type=int)
    if person_id is None:
        return jsonify({"error": "Person is required"}), 400
    with dependency("connect")() as connection:
        people = PersonRepository(connection).list_all()
        repository = AnnualEmploymentActualRepository(connection)
        if year is None:
            records = list(reversed(repository.list_for_person(person_id)))
            record = None
        else:
            records = []
            record = repository.get(person_id, year)
    return jsonify(
        {
            "people": [{"id": person.id, "name": person.name} for person in people],
            "person_id": person_id,
            "year": year,
            "record": _record_json(record) if record else None,
            "records": [_record_json(item) for item in records],
        }
    )


@blueprint.put("/api/income/people/<int:person_id>/years/<int:year>")
def save_income_record(person_id: int, year: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            record = AnnualEmploymentActualRepository(connection).upsert(
                person_id,
                year,
                _amount(payload, "employment_income"),
                province_of_employment=str(payload.get("province_of_employment") or ""),
                bonus=_amount(payload, "bonus"),
                other_income=_amount(payload, "other_income"),
                rrsp_contribution=_amount(payload, "rrsp_contribution"),
                rrsp_deduction=_amount(payload, "rrsp_deduction"),
                cpp_qpp=_amount(payload, "cpp_qpp"),
                ei=_amount(payload, "ei"),
                qpip=_amount(payload, "qpip"),
                federal_tax=_amount(payload, "federal_tax"),
                provincial_tax=_amount(payload, "provincial_tax"),
                source=str(payload.get("source") or "T1 / manual"),
            )
        return jsonify(_record_json(record))
    except (TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/income/import/ufile/preview")
def preview_ufile_tax_return():
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify({"error": "UFile tax return PDF is required"}), 400
    try:
        parsed = UFileTaxReturnParser().parse(uploaded.read())
        return jsonify(
            {
                "year": parsed.tax_year,
                "employment_income": _money(parsed.employment_income),
                "bonus": "0.00",
                "salary_rate": _money(parsed.employment_income),
                "other_income": _money(parsed.other_employment_income),
                "cpp_qpp": _money(parsed.cpp_qpp),
                "ei": _money(parsed.ei),
                "qpip": _money(parsed.qpip),
                "rrsp_contribution": _money(parsed.rrsp_contribution),
                "rrsp_deduction": _money(parsed.rrsp_deduction),
                "federal_tax": _money(parsed.federal_tax),
                "provincial_tax": _money(parsed.provincial_tax),
                "source": "UFile T1",
                "province_of_employment": "",
            }
        )
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


def _amount(payload: dict[str, Any], name: str) -> Decimal:
    return as_decimal(payload.get(name, 0))


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _record_json(record: AnnualEmploymentActual) -> dict[str, Any]:
    return {
        "id": record.id,
        "person_id": record.person_id,
        "year": record.tax_year,
        "province_of_employment": record.province_of_employment,
        "payroll_plan": record.payroll_plan,
        "employment_income": _money(record.salary_income),
        "bonus": _money(record.bonus),
        "salary_rate": _money(record.salary_rate),
        "other_income": _money(record.other_income),
        "gross_income": _money(record.gross_income),
        "rrsp_contribution": _money(record.rrsp_contribution),
        "rrsp_deduction": _money(record.rrsp_deduction),
        "cpp_qpp": _money(record.cpp_qpp),
        "ei": _money(record.ei),
        "qpip": _money(record.qpip),
        "federal_tax": _money(record.federal_tax),
        "provincial_tax": _money(record.provincial_tax),
        "disposable_income": _money(record.disposable_income),
        "source": record.source or "T1 / manual",
    }
