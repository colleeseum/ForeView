# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, jsonify, render_template, request

from repositories.expense_repository import ExpenseRepository
from services.expense_service import ExpenseService

blueprint = Blueprint("expenses", __name__)


def _connection():
    return current_app.extensions["finance_connect"]()


def _record(record):
    return {
        "id": record.id, "name": record.name, "category_id": record.category_id,
        "category_name": record.category_name, "classification": record.classification,
        "amount": str(record.amount), "period_start": record.period_start,
        "period_end": record.period_end, "source_kind": record.source_kind,
        "source_document_id": record.source_document_id, "source_name": record.source_name,
        "parser_name": record.parser_name, "parser_version": record.parser_version,
        "source_hash": record.source_hash, "association_kind": record.association_kind,
        "association_id": record.association_id, "overlap_status": record.overlap_status,
        "overlap_resolution_note": record.overlap_resolution_note,
        "created_at": record.created_at, "updated_at": record.updated_at,
    }


@blueprint.get("/expenses")
def expenses_page():
    connection = _connection()
    try:
        repository = ExpenseRepository(connection)
        year_text = request.args.get("year")
        year = int(year_text) if year_text else date.today().year
        return render_template(
            "expenses.html", year=year, summary=repository.totals_for_year(year),
            expenses=repository.list_expenses(year=year),
            categories=repository.list_categories(include_inactive=True),
        )
    finally:
        connection.close()


@blueprint.get("/api/expenses")
def list_expenses():
    connection = _connection()
    try:
        year = request.args.get("year", type=int)
        return jsonify([_record(record) for record in ExpenseRepository(connection).list_expenses(year=year)])
    finally:
        connection.close()


@blueprint.post("/api/expenses/categories")
def create_category():
    payload = request.get_json(silent=True) or request.form
    connection = _connection()
    try:
        category = ExpenseService(connection).create_category(
            str(payload.get("name", "")), str(payload.get("classification", ""))  # type: ignore[arg-type]
        )
        return jsonify({"id": category.id, "name": category.name,
                        "classification": category.classification, "is_active": category.is_active}), 201
    finally:
        connection.close()


@blueprint.post("/api/expenses/manual")
def create_manual_expense():
    payload = request.get_json(silent=True) or request.form
    connection = _connection()
    try:
        record = ExpenseService(connection).create_manual(
            name=str(payload.get("name", "")), category_id=int(payload["category_id"]),
            amount=str(payload["amount"]), period_start=date.fromisoformat(str(payload["period_start"])),
            period_end=date.fromisoformat(str(payload["period_end"])),
            association_kind=str(payload.get("association_kind", "household")),  # type: ignore[arg-type]
            association_id=int(payload["association_id"]) if payload.get("association_id") else None,
        )
        return jsonify(_record(record)), 201
    finally:
        connection.close()


@blueprint.post("/api/expenses/imported/confirm")
def confirm_imported_expense():
    payload = request.get_json(silent=True) or request.form
    connection = _connection()
    try:
        record = ExpenseService(connection).confirm_import(
            name=str(payload.get("name", "")), category_id=int(payload["category_id"]),
            amount=str(payload["amount"]), period_start=date.fromisoformat(str(payload["period_start"])),
            period_end=date.fromisoformat(str(payload["period_end"])),
            source_document_id=int(payload["source_document_id"]), source_name=str(payload["source_name"]),
            parser_name=str(payload["parser_name"]), parser_version=str(payload["parser_version"]) if payload.get("parser_version") else None,
            source_hash=str(payload["source_hash"]), association_kind=str(payload.get("association_kind", "household")),  # type: ignore[arg-type]
            association_id=int(payload["association_id"]) if payload.get("association_id") else None,
        )
        return jsonify(_record(record)), 201
    finally:
        connection.close()


@blueprint.post("/api/expenses/<int:expense_id>/overlap")
def resolve_overlap(expense_id: int):
    payload = request.get_json(silent=True) or request.form
    connection = _connection()
    try:
        with connection:
            record = ExpenseRepository(connection).resolve_overlap(
                expense_id, include=bool(payload.get("include")), note=str(payload.get("note", ""))
            )
        return jsonify(_record(record))
    finally:
        connection.close()
