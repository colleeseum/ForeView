# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, TypedDict, cast

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from domain.expense import ExpenseRecord
from domain.validation_error import ValidationError
from domain.validation_lookup_error import ValidationLookupError
from expense_sources import expense_source_registry
from localization import LocalizationService
from repositories.account_repository import AccountRepository
from repositories.expense_repository import ExpenseRepository
from repositories.person_repository import PersonRepository
from repositories.real_estate_asset_repository import RealEstateAssetRepository
from services.expenses.expense_import_service import ExpenseImportService
from services.expenses.expense_service import ExpenseService
from web.dependencies import dependency
from web.localization import localized_api_error, localized_error_data, provider_presentation

blueprint = Blueprint("expenses", __name__)


class _PageError(TypedDict):
    error: str
    error_language: str


def _expense_error_data(error: Exception) -> dict[str, str]:
    if isinstance(error, (ValidationError, ValidationLookupError)):
        return localized_error_data(error.code, **error.values)
    return {"error": str(error), "error_language": "en-CA"}


def _page_error(error: Exception) -> _PageError:
    data = _expense_error_data(error)
    return {"error": data["error"], "error_language": data["error_language"]}


def _redirect_error(year: int, error: Exception, *, dialog: str | None = None):
    return _redirect(year, **_page_error(error), dialog=dialog)


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValidationError("expense_integer", str(error), value=repr(value)) from error


def _required(payload: dict[str, Any], field: str) -> Any:
    try:
        return payload[field]
    except KeyError as error:
        raise ValidationError("expense_field_required", str(error), field=field) from error


def _calendar_date(value: object) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise ValidationError("expense_date", str(error), value=repr(value)) from error


def _record(record: ExpenseRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "deletion_token": ExpenseService.deletion_token(record),
        "name": record.name,
        "category_id": record.category_id,
        "category_name": record.category_name,
        "classification": record.classification,
        "amount": str(record.amount),
        "period_start": record.period_start,
        "period_end": record.period_end,
        "source_kind": record.source_kind,
        "source_document_id": record.source_document_id,
        "source_name": record.source_name,
        "parser_name": record.parser_name,
        "parser_version": record.parser_version,
        "source_hash": record.source_hash,
        "association_kind": record.association_kind,
        "association_id": record.association_id,
        "overlap_status": record.overlap_status,
        "period_kind": record.period_kind,
        "overlap_resolution_note": record.overlap_resolution_note,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _payload() -> dict[str, Any]:
    values = request.get_json(silent=True) if request.is_json else request.form
    return dict(values or {})


def _association(payload: dict[str, Any]) -> tuple[str, int | None]:
    combined = str(payload.get("association", "")).strip()
    if combined:
        kind, separator, identifier = combined.partition(":")
        return kind, _integer(identifier) if separator and identifier else None
    kind = str(payload.get("association_kind", "household"))
    raw_identifier = payload.get("association_id")
    if raw_identifier in (None, ""):
        return kind, None
    return kind, _integer(str(raw_identifier))


def _parse_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "include", "active"}:
        return True
    if normalized in {"false", "0", "no", "exclude", "inactive"}:
        return False
    raise ValidationError("expense_boolean", "Expected a true or false value")


def _year(payload: dict[str, Any] | None = None) -> int:
    raw = (payload or {}).get("year", request.args.get("year", date.today().year))
    year = _integer(raw)
    if year < 1900 or year > 9999:
        raise ValidationError("expense_year", "Expense year must be between 1900 and 9999")
    return year


def _page(
    year: int,
    *,
    error: str | None = None,
    error_language: str = "en-CA",
    message: str | None = None,
    open_dialog: str | None = None,
    imported_count: int = 0,
    imported_years: tuple[int, ...] = (),
):
    with dependency("connect")() as connection:
        repository = ExpenseRepository(connection)
        available_years = repository.available_years()
        if year not in available_years:
            available_years.append(year)
            available_years.sort(reverse=True)
        return render_template(
            "expenses.html",
            year=year,
            available_years=available_years,
            summary=repository.totals_for_year(year),
            expenses=repository.list_expenses(year=year),
            categories=repository.list_categories(include_inactive=True),
            people=PersonRepository(connection).list_all(),
            accounts=AccountRepository(connection).summary_rows(),
            real_estate=RealEstateAssetRepository(connection).list_all(),
            expense_deletion_token=ExpenseService.deletion_token,
            error=error,
            error_language=error_language,
            message=message,
            open_dialog=open_dialog,
            imported_count=imported_count,
            imported_years=imported_years,
        )


def _redirect(
    year: int,
    *,
    error: str | None = None,
    error_language: str | None = None,
    message: str | None = None,
    dialog: str | None = None,
):
    return redirect(
        url_for(
            "expenses.expenses_page",
            year=year,
            error=error,
            error_language=error_language,
            message=message,
            dialog=dialog,
        )
    )


def _localized_message(key: str) -> str:
    localization: LocalizationService = current_app.extensions["localization"]
    locale = localization.selected_locale()
    return localization.translate(locale, f"pages_server.expenses.{key}")


@blueprint.get("/expenses")
def expenses_page():
    try:
        imported_count = _integer(request.args.get("imported", "0"))
        if imported_count < 0:
            raise ValidationError(
                "expense_import_count", "Imported statement count cannot be negative"
            )
        imported_years = tuple(
            sorted(
                {
                    _integer(value)
                    for value in request.args.get("imported_years", "").split(",")
                    if value
                }
            )
        )
        if any(year < 1900 or year > 9999 for year in imported_years):
            raise ValidationError(
                "expense_import_year", "Imported expense years must be between 1900 and 9999"
            )
        return _page(
            _year(),
            error=request.args.get("error"),
            error_language=current_app.extensions["localization"]
            .definition(request.args.get("error_language", "en-CA"))
            .code,
            message=request.args.get("message"),
            open_dialog=("categories" if request.args.get("dialog") == "categories" else None),
            imported_count=imported_count,
            imported_years=imported_years,
        )
    except (TypeError, ValueError) as error:
        return _page(date.today().year, **_page_error(error)), 400


@blueprint.get("/api/expenses")
def list_expenses():
    try:
        year = _year() if request.args.get("year") is not None else None
        with dependency("connect")() as connection:
            records = ExpenseRepository(connection).list_expenses(year=year)
        return jsonify([_record(record) for record in records])
    except (TypeError, ValueError) as error:
        return jsonify(_expense_error_data(error)), 400


def _create_category(payload: dict[str, Any]):
    with dependency("connect")() as connection:
        return ExpenseService(connection).create_category(
            str(payload.get("name", "")),
            str(payload.get("classification", "")),  # type: ignore[arg-type]
        )


@blueprint.post("/api/expenses/categories")
def create_category():
    try:
        category = _create_category(_payload())
        return jsonify(
            {
                "id": category.id,
                "name": category.name,
                "classification": category.classification,
                "is_active": category.is_active,
            }
        ), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify(_expense_error_data(error)), 400


@blueprint.post("/expenses/categories")
def create_category_form():
    payload = _payload()
    year = date.today().year
    try:
        year = _year(payload)
        _create_category(payload)
        return _redirect(year, message=_localized_message("category_created"), dialog="categories")
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return _redirect_error(year, error, dialog="categories")


def _update_category(category_id: int, payload: dict[str, Any]):
    with dependency("connect")() as connection:
        return ExpenseService(connection).update_category(
            category_id,
            name=str(payload.get("name", "")),
            classification=str(payload.get("classification", "")),  # type: ignore[arg-type]
            active=_parse_boolean(payload.get("active", True)),
        )


@blueprint.put("/api/expenses/categories/<int:category_id>")
def update_category(category_id: int):
    try:
        category = _update_category(category_id, _payload())
        return jsonify(
            {
                "id": category.id,
                "name": category.name,
                "classification": category.classification,
                "is_active": category.is_active,
            }
        )
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify(_expense_error_data(error)), 400


@blueprint.post("/expenses/categories/<int:category_id>")
def update_category_form(category_id: int):
    payload = _payload()
    year = date.today().year
    try:
        year = _year(payload)
        _update_category(category_id, payload)
        return _redirect(year, message=_localized_message("category_updated"), dialog="categories")
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return _redirect_error(year, error, dialog="categories")


def _create_manual(payload: dict[str, Any]):
    association_kind, association_id = _association(payload)
    with dependency("connect")() as connection:
        return ExpenseService(connection).create_manual(
            name=str(payload.get("name", "")),
            category_id=_integer(_required(payload, "category_id")),
            amount=str(_required(payload, "amount")),
            period_start=_calendar_date(_required(payload, "period_start")),
            period_end=_calendar_date(_required(payload, "period_end")),
            association_kind=association_kind,  # type: ignore[arg-type]
            association_id=association_id,
            period_kind=str(payload.get("period_kind", "annual_or_one_time")),  # type: ignore[arg-type]
        )


@blueprint.post("/api/expenses/manual")
def create_manual_expense():
    try:
        return jsonify(_record(_create_manual(_payload()))), 201
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify(_expense_error_data(error)), 400


@blueprint.post("/expenses/manual")
def create_manual_expense_form():
    payload = _payload()
    year = date.today().year
    try:
        year = _year(payload)
        _create_manual(payload)
        return _redirect(year, message=_localized_message("factual_saved"))
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return _redirect_error(year, error)


@blueprint.delete("/api/expenses/<int:expense_id>")
def delete_expense(expense_id: int):
    try:
        token = str(_required(_payload(), "expected_token"))
        with dependency("connect")() as connection:
            ExpenseService(connection).delete_imported(expense_id, expected_token=token)
        return "", 204
    except ValidationLookupError as error:
        return jsonify(_expense_error_data(error)), 404
    except ValidationError as error:
        return jsonify(
            _expense_error_data(error)
        ), 409 if error.code == "expense_delete_stale" else 400
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify(_expense_error_data(error)), 400


@blueprint.put("/api/expenses/<int:expense_id>")
def update_expense(expense_id: int):
    payload = _payload()
    try:
        association_kind, association_id = _association(payload)
        with dependency("connect")() as connection:
            record = ExpenseService(connection).update_manual(
                expense_id,
                name=str(payload.get("name", "")),
                category_id=_integer(_required(payload, "category_id")),
                amount=str(_required(payload, "amount")),
                period_start=_calendar_date(_required(payload, "period_start")),
                period_end=_calendar_date(_required(payload, "period_end")),
                association_kind=association_kind,  # type: ignore[arg-type]
                association_id=association_id,
                period_kind=str(payload.get("period_kind", "annual_or_one_time")),  # type: ignore[arg-type]
            )
        return jsonify(_record(record))
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify(_expense_error_data(error)), 400


def _resolve_overlap(expense_id: int, payload: dict[str, Any]):
    with dependency("connect")() as connection:
        return ExpenseService(connection).resolve_overlap(
            expense_id,
            include=_parse_boolean(payload.get("include")),
            note=str(payload.get("note", "")),
        )


@blueprint.post("/api/expenses/<int:expense_id>/overlap")
def resolve_overlap(expense_id: int):
    try:
        return jsonify(_record(_resolve_overlap(expense_id, _payload())))
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify(_expense_error_data(error)), 400


@blueprint.post("/expenses/<int:expense_id>/overlap")
def resolve_overlap_form(expense_id: int):
    payload = _payload()
    year = date.today().year
    try:
        year = _year(payload)
        _resolve_overlap(expense_id, payload)
        return _redirect(year, message=_localized_message("overlap_saved"))
    except (KeyError, LookupError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return _redirect_error(year, error)


# ----------------------------------------------------------------------
# Imported-expense preview and confirmation
# ----------------------------------------------------------------------


@blueprint.post("/api/expenses/import/preview")
def import_expense_preview():
    """Detect + parse a PDF and return reviewable evidence without persisting."""
    try:
        pdf_file = request.files.get("file")
        if not pdf_file or not pdf_file.filename:
            return localized_api_error("expense_pdf_required")

        content = pdf_file.read()
        filename = pdf_file.filename

        with dependency("connect")() as connection:
            preview = ExpenseImportService(connection).preview(content, source_filename=filename)

        provider = expense_source_registry.get(preview.provider_key)
        presentation = provider_presentation(provider.display_name, provider.translations)
        payload = preview.to_dict()
        payload["provider_display_name"] = presentation["display_name"]
        payload["provider_display_language"] = cast(
            dict[str, str], presentation["field_languages"]
        )["display_name"]
        return jsonify({"preview": payload})
    except (TypeError, ValueError, LookupError) as error:
        return jsonify(_expense_error_data(error)), 400


@blueprint.post("/api/expenses/import/confirm")
def import_expense_confirm():
    """Re-parse the uploaded PDF and persist a factual expense record."""
    try:
        form = request.form
        pdf_file = request.files.get("file")
        if not pdf_file or not pdf_file.filename:
            return localized_api_error("expense_pdf_required")

        content = pdf_file.read()
        payload = dict(form)
        association_kind, association_id = _association(payload)

        with dependency("connect")() as connection:
            record = ExpenseImportService(connection).confirm(
                content=content,
                source_filename=pdf_file.filename,
                provider_key=str(payload.get("provider_key", "")),
                name=str(payload.get("name", "")),
                category_id=_integer(_required(payload, "category_id")),
                association_kind=association_kind,  # type: ignore[arg-type]
                association_id=association_id,
            )

        return jsonify(_record(record)), 201
    except (TypeError, ValueError, LookupError, KeyError, sqlite3.IntegrityError) as error:
        return jsonify(_expense_error_data(error)), 400
