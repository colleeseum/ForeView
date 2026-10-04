# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from decimal import Decimal
from hashlib import sha256
from typing import Any

from flask import Blueprint, jsonify, request

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.money import as_decimal
from domain.parsed_tax_value import ParsedTaxValue
from income_sources import income_source_registry
from public_pension_sources import public_pension_source_registry
from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.annual_tax_assessment_repository import AnnualTaxAssessmentRepository
from repositories.annual_tax_value_repository import AnnualTaxValueRepository
from repositories.correction_repository import CorrectionRepository
from repositories.person_repository import PersonRepository
from repositories.public_pension_statement_repository import PublicPensionStatementRepository
from repositories.registered_plan_room_repository import RegisteredPlanRoomRepository
from services.income_tax_snapshot_service import IncomeTaxSnapshotService
from services.income_tax_source_resolver import IncomeTaxSourceResolver
from tax_notices import tax_notice_registry
from web.correction_serialization import correction_revision_json
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
        all_records = list(reversed(repository.list_for_person(person_id)))
        assessments = AnnualTaxAssessmentRepository(connection).list_for_person(person_id)
        rooms = RegisteredPlanRoomRepository(connection).list_for_person(person_id)
        pension_repository = PublicPensionStatementRepository(connection)
        tax_value_repository = AnnualTaxValueRepository(connection)
        tax_values = tax_value_repository.list_for_person(person_id)
        pension = pension_repository.latest_for_person(person_id)

        # Create service with correction repository
        correction_repository = CorrectionRepository(connection)
        snapshot_service = IncomeTaxSnapshotService(correction_repository=correction_repository)
        snapshot = snapshot_service.build(
            all_records, assessments, tax_values, person_id=person_id, year=year
        )
        corrections: list[dict[str, Any]] = []
        if snapshot is not None:
            source_resolver = IncomeTaxSourceResolver(all_records, assessments, tax_values)
            corrections = [
                correction_revision_json(
                    revision,
                    source_resolver.resolve(snapshot.tax_year, revision.concept),
                )
                for revision in correction_repository.list_for_year(person_id, snapshot.tax_year)
            ]
        if year is None:
            records = all_records
            record = None
        else:
            records = []
            record = repository.get(person_id, year)
        public_pension = _pension_json(pension_repository, pension) if pension else None
    return jsonify(
        {
            "people": [{"id": person.id, "name": person.name} for person in people],
            "person_id": person_id,
            "year": year,
            "record": _record_json(record, tax_values) if record else None,
            "records": [_record_json(item, tax_values) for item in records],
            "assessments": [_assessment_json(item) for item in assessments],
            "registered_rooms": [_room_json(item) for item in rooms],
            "public_pension": public_pension,
            "tax_values": [_tax_value_json(item) for item in tax_values],
            "snapshot": _snapshot_json(snapshot) if snapshot else None,
            "corrections": corrections,
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
                province_of_residence=str(payload.get("province_of_residence") or ""),
                payroll_plan=str(payload.get("payroll_plan") or "") or None,
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
            tax_repository = AnnualTaxValueRepository(connection)
            source = str(payload.get("source") or "Manual")
            source_version = str(payload.get("source_version") or "manual")
            document_hash = str(payload.get("document_hash") or "manual")
            if "tax_values" in payload:
                tax_repository.replace_document(
                    person_id,
                    year,
                    "return",
                    "CA",
                    source,
                    source_version,
                    document_hash,
                    _parsed_tax_values(payload.get("tax_values")),
                )
            elif "interest_income" in payload:
                tax_repository.upsert_value(
                    person_id,
                    year,
                    "return",
                    "CA",
                    source,
                    source_version,
                    document_hash,
                    ParsedTaxValue(
                        "interest_investment_income",
                        "Interest and other investment income",
                        _amount(payload, "interest_income"),
                        line_code="12100",
                        effective_year=year,
                    ),
                )
            tax_values = tax_repository.list_for_document(person_id, year, "return", "CA")
        return jsonify(_record_json(record, tax_values))
    except (TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/income/import/preview")
def preview_income_source():
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify({"error": "An income source PDF is required"}), 400
    try:
        content = uploaded.read()
        content_hash = sha256(content).hexdigest()
        notice_source = tax_notice_registry.detect(content)
        if notice_source:
            parsed_notice = notice_source.parser(content)
            return jsonify(
                {
                    "kind": "tax_assessment",
                    "tax_year": parsed_notice.tax_year,
                    "jurisdiction": parsed_notice.jurisdiction,
                    "issued_on": parsed_notice.issued_on,
                    "taxpayer_name": parsed_notice.taxpayer_name or "",
                    "total_income": _money(parsed_notice.total_income),
                    "net_income": _money(parsed_notice.net_income),
                    "taxable_income": _money(parsed_notice.taxable_income),
                    "net_tax": _money(parsed_notice.net_tax),
                    "additional_contributions": _money(parsed_notice.additional_contributions),
                    "tax_withheld": _money(parsed_notice.tax_withheld),
                    "balance": _money(parsed_notice.balance),
                    "rrsp_effective_year": parsed_notice.rrsp_effective_year,
                    "rrsp_deduction_limit": _optional_money(parsed_notice.rrsp_deduction_limit),
                    "rrsp_unused_deduction_room": _optional_money(
                        parsed_notice.rrsp_unused_deduction_room
                    ),
                    "rrsp_new_room": _optional_money(parsed_notice.rrsp_new_room),
                    "rrsp_unused_contributions": _optional_money(
                        parsed_notice.rrsp_unused_contributions
                    ),
                    "rrsp_available_room": _optional_money(parsed_notice.rrsp_available_room),
                    "source": notice_source.source_label,
                    "source_name": notice_source.display_name,
                    "source_version": notice_source.version,
                    "document_hash": content_hash,
                    "tax_values": [
                        _parsed_tax_value_json(value) for value in parsed_notice.tax_values
                    ],
                }
            )
        pension_source = public_pension_source_registry.detect(content)
        if pension_source:
            parsed_pension = pension_source.parser(content)
            return jsonify(
                {
                    "kind": "public_pension_statement",
                    "issued_on": parsed_pension.issued_on,
                    "taxpayer_name": parsed_pension.taxpayer_name or "",
                    "birth_date": parsed_pension.birth_date,
                    "provider": parsed_pension.provider,
                    "excludes_second_enhancement": parsed_pension.excludes_second_enhancement,
                    "earnings": [
                        {
                            "year": year,
                            "qpp_earnings": _money(qpp),
                            "cpp_earnings": _money(cpp),
                            "status": status,
                        }
                        for year, qpp, cpp, status in parsed_pension.earnings
                    ],
                    "estimates": [
                        {
                            "contribution_assumption": assumption,
                            "activation_age": age,
                            "monthly_amount": _money(amount),
                        }
                        for assumption, age, amount in parsed_pension.estimates
                    ],
                    "source_name": pension_source.display_name,
                    "source_version": pension_source.version,
                    "document_hash": content_hash,
                }
            )
        requested_source = request.form.get("source", "auto")
        source = (
            income_source_registry.detect(content)
            if requested_source in {"", "auto"}
            else income_source_registry.get(requested_source)
        )
        parsed = source.parser(content)
        return jsonify(
            {
                "kind": "tax_return",
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
                "source": source.source_label,
                "source_key": source.key,
                "source_name": source.display_name,
                "source_version": source.version,
                "source_help": source.help_text,
                "province_of_residence": parsed.province_of_residence or "",
                "payroll_plan": parsed.payroll_plan or "",
                "taxpayer_name": parsed.taxpayer_name or "",
                "jurisdiction": "CA",
                "document_hash": content_hash,
                "interest_income": _parsed_concept_amount(
                    parsed.tax_values, "interest_investment_income"
                ),
                "tax_values": [_parsed_tax_value_json(value) for value in parsed.tax_values],
            }
        )
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/income/people/<int:person_id>/assessments")
def save_tax_assessment(person_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            assessment = AnnualTaxAssessmentRepository(connection).upsert(
                person_id,
                int(payload["tax_year"]),
                str(payload["jurisdiction"]),
                str(payload["issued_on"]),
                total_income=_amount(payload, "total_income"),
                net_income=_amount(payload, "net_income"),
                taxable_income=_amount(payload, "taxable_income"),
                net_tax=_amount(payload, "net_tax"),
                additional_contributions=_amount(payload, "additional_contributions"),
                tax_withheld=_amount(payload, "tax_withheld"),
                balance=_amount(payload, "balance"),
                source=str(payload["source"]),
                source_version=str(payload["source_version"]),
                document_hash=str(payload["document_hash"]),
            )
            if payload.get("rrsp_effective_year") is not None:
                RegisteredPlanRoomRepository(connection).upsert(
                    person_id,
                    "RRSP",
                    int(payload["rrsp_effective_year"]),
                    str(payload["issued_on"]),
                    deduction_limit=_amount(payload, "rrsp_deduction_limit"),
                    unused_deduction_room=_amount(payload, "rrsp_unused_deduction_room"),
                    new_room=_amount(payload, "rrsp_new_room"),
                    unused_contributions=_amount(payload, "rrsp_unused_contributions"),
                    available_room=_amount(payload, "rrsp_available_room"),
                    source=str(payload["source"]),
                    source_version=str(payload["source_version"]),
                )
            if "tax_values" in payload:
                AnnualTaxValueRepository(connection).replace_document(
                    person_id,
                    int(payload["tax_year"]),
                    "assessment",
                    str(payload["jurisdiction"]),
                    str(payload["source"]),
                    str(payload["source_version"]),
                    str(payload["document_hash"]),
                    _parsed_tax_values(payload.get("tax_values")),
                )
        return jsonify(_assessment_json(assessment)), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/income/people/<int:person_id>/public-pension-statements")
def save_public_pension_statement(person_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        earnings = tuple(
            (
                int(item["year"]),
                as_decimal(item["qpp_earnings"]),
                as_decimal(item["cpp_earnings"]),
                str(item["status"]) if item.get("status") else None,
            )
            for item in payload["earnings"]
        )
        estimates = tuple(
            (
                str(item["contribution_assumption"]),
                int(item["activation_age"]),
                as_decimal(item["monthly_amount"]),
            )
            for item in payload["estimates"]
        )
        with dependency("connect")() as connection:
            repository = PublicPensionStatementRepository(connection)
            statement = repository.upsert(
                person_id,
                str(payload["issued_on"]),
                str(payload["provider"]),
                bool(payload.get("excludes_second_enhancement")),
                str(payload["source_version"]),
                str(payload["document_hash"]),
                earnings,
                estimates,
            )
        return jsonify({"id": statement.id, "issued_on": statement.issued_on}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/income/import/ufile/preview")
def preview_ufile_tax_return():
    """Compatibility endpoint for existing clients."""
    return preview_income_source()


@blueprint.get("/api/income/sources")
def income_sources():
    return jsonify(
        {
            "sources": [
                {
                    "key": source.key,
                    "display_name": source.display_name,
                    "version": source.version,
                    "help_text": source.help_text,
                }
                for source in income_source_registry.providers
            ]
        }
    )


def _amount(payload: dict[str, Any], name: str) -> Decimal:
    return as_decimal(payload.get(name, 0))


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _optional_money(value: Decimal | None) -> str | None:
    return _money(value) if value is not None else None


def _record_json(
    record: AnnualEmploymentActual, tax_values: list[Any] | tuple[Any, ...] = ()
) -> dict[str, Any]:
    record_values = [
        value
        for value in tax_values
        if value.tax_year == record.tax_year
        and value.document_kind == "return"
        and value.jurisdiction == "CA"
    ]
    interest = next(
        (
            value.reported_amount
            for value in record_values
            if value.concept == "interest_investment_income"
        ),
        Decimal("0"),
    )
    return {
        "id": record.id,
        "person_id": record.person_id,
        "year": record.tax_year,
        "province_of_residence": record.province_of_residence,
        "payroll_plan": record.payroll_plan,
        "employment_income": _money(record.salary_income),
        "bonus": _money(record.bonus),
        "salary_rate": _money(record.salary_rate),
        "other_income": _money(record.other_income),
        "interest_income": _money(interest or Decimal("0")),
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
        "tax_values": [_tax_value_json(value) for value in record_values],
    }


def _parsed_tax_values(raw_values: Any) -> tuple[ParsedTaxValue, ...]:
    if not isinstance(raw_values, list):
        raise ValueError("Tax values must be a list")
    return tuple(
        ParsedTaxValue(
            concept=str(item["concept"]),
            description=str(item["description"]),
            reported_amount=(
                as_decimal(item["reported_amount"])
                if item.get("reported_amount") is not None
                else None
            ),
            determined_amount=(
                as_decimal(item["determined_amount"])
                if item.get("determined_amount") is not None
                else None
            ),
            line_code=str(item["line_code"]) if item.get("line_code") else None,
            effective_year=(
                int(item["effective_year"]) if item.get("effective_year") is not None else None
            ),
        )
        for item in raw_values
        if isinstance(item, dict)
    )


def _parsed_tax_value_json(value: ParsedTaxValue) -> dict[str, Any]:
    return {
        "concept": value.concept,
        "description": value.description,
        "reported_amount": _optional_money(value.reported_amount),
        "determined_amount": _optional_money(value.determined_amount),
        "line_code": value.line_code,
        "effective_year": value.effective_year,
    }


def _parsed_concept_amount(values: tuple[ParsedTaxValue, ...], concept: str) -> str:
    amount = next(
        (value.reported_amount for value in values if value.concept == concept),
        Decimal("0"),
    )
    return _money(amount or Decimal("0"))


def _tax_value_json(value: Any) -> dict[str, Any]:
    return {
        "id": value.id,
        "tax_year": value.tax_year,
        "effective_year": value.effective_year,
        "document_kind": value.document_kind,
        "jurisdiction": value.jurisdiction,
        "concept": value.concept,
        "description": value.description,
        "reported_amount": _optional_money(value.reported_amount),
        "determined_amount": _optional_money(value.determined_amount),
        "line_code": value.line_code,
        "source": value.source,
        "source_version": value.source_version,
    }


def _snapshot_json(snapshot: Any) -> dict[str, Any]:
    return {
        "tax_year": snapshot.tax_year,
        "available_years": list(snapshot.available_years),
        "values": [
            {
                "concept": value.concept,
                "label": value.label,
                "amount": _money(value.amount),
                "source": value.source,
                "document_kind": value.document_kind,
                "jurisdiction": value.jurisdiction,
                "line_code": value.line_code,
            }
            for value in snapshot.values
        ],
    }


def _assessment_json(record: Any) -> dict[str, Any]:
    return {
        "id": record.id,
        "year": record.tax_year,
        "jurisdiction": record.jurisdiction,
        "issued_on": record.issued_on,
        "total_income": _money(record.total_income),
        "net_income": _money(record.net_income),
        "taxable_income": _money(record.taxable_income),
        "net_tax": _money(record.net_tax),
        "additional_contributions": _money(record.additional_contributions),
        "tax_withheld": _money(record.tax_withheld),
        "balance": _money(record.balance),
        "source": record.source,
        "source_version": record.source_version,
    }


def _room_json(record: Any) -> dict[str, Any]:
    return {
        "id": record.id,
        "plan_type": record.plan_type,
        "effective_year": record.effective_year,
        "as_of_date": record.as_of_date,
        "deduction_limit": _money(record.deduction_limit),
        "unused_deduction_room": _money(record.unused_deduction_room),
        "new_room": _money(record.new_room),
        "unused_contributions": _money(record.unused_contributions),
        "available_room": _money(record.available_room),
        "source": record.source,
        "source_version": record.source_version,
    }


def _pension_json(repository: Any, statement: Any) -> dict[str, Any]:
    return {
        "id": statement.id,
        "issued_on": statement.issued_on,
        "provider": statement.provider,
        "excludes_second_enhancement": statement.excludes_second_enhancement,
        "source_version": statement.source_version,
        "earnings": [
            {
                "year": item.year,
                "qpp_earnings": _money(item.qpp_earnings),
                "cpp_earnings": _money(item.cpp_earnings),
                "status": item.status,
            }
            for item in repository.earnings(statement.id)
        ],
        "estimates": [
            {
                "contribution_assumption": item.contribution_assumption,
                "activation_age": item.activation_age,
                "monthly_amount": _money(item.monthly_amount),
            }
            for item in repository.estimates(statement.id)
        ],
    }
