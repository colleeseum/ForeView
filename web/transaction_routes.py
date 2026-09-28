from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import jsonify, request

from domain.money import as_decimal
from domain.reconciliation_checkpoint import ReconciliationCheckpoint
from ingestion.reconciled_period_change import ReconciledPeriodChange
from institution_support.document_detection import detect_importer
from institution_support.registry import institution_registry
from institutions.eq.document_importers import import_eq_statement_pdf
from repositories.account_repository import AccountRepository
from services.csv_import_service import CsvImportService
from services.document_import_account_resolver import DocumentImportAccountResolver
from services.reconciliation_checkpoint_service import ReconciliationCheckpointService
from services.transaction_service import TransactionService
from web.dependencies import dependency
from web.model_blueprint import blueprint
from web.route_values import payload_bool


def _import_csv(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | str]:
    return CsvImportService(connection).import_transactions(
        account_id, filename, content, allow_reconciled=allow_reconciled
    )


@blueprint.post("/api/model/transactions/import")
def import_transactions_route():
    account_id = request.form.get("account_id")
    # Set when the user confirmed importing into an already-reconciled period.
    allow_reconciled = payload_bool(request.form.get("confirm_reconciled", False))
    uploaded_files = [
        item
        for item in request.files.getlist("files")
        if item and item.filename and not Path(item.filename).name.startswith(".")
    ]
    if not account_id or not uploaded_files:
        return jsonify(
            {
                "error": "Choose an account, Auto-detect, and at least one PDF or CSV file.",
                "help_url": "/transactions#transaction-import-help",
            }
        ), 400
    try:
        with dependency("connect")() as connection:
            results: list[dict[str, object]] = []
            for item in uploaded_files:
                try:
                    filename = item.filename
                    if not filename:
                        continue
                    content = item.read()
                    auto_detect = account_id == "auto"
                    is_pdf = content.startswith(b"%PDF-") or filename.lower().endswith(".pdf")
                    if is_pdf:
                        selected_account = (
                            None
                            if auto_detect
                            else AccountRepository(connection).get(int(account_id))
                        )
                        detected = detect_importer(
                            content, selected_account.institution if selected_account else None
                        )
                        if auto_detect and not detected:
                            raise ValueError(
                                "Could not identify an account from this PDF. Choose an existing account."
                            )
                        importer = detected.importer if detected else import_eq_statement_pdf
                        resolved_account_id = (
                            DocumentImportAccountResolver(
                                connection, institution_registry()
                            ).resolve(detected.spec.importer_name, content, filename)
                            if auto_detect and detected
                            else (None if auto_detect else int(account_id))
                        )
                    else:
                        if auto_detect:
                            raise ValueError(
                                "Auto-detect is supported for PDFs. Choose an account for CSV files."
                            )
                        importer = _import_csv
                        resolved_account_id = int(account_id)
                    if resolved_account_id is None:
                        raise ValueError("Could not resolve an account for this import.")
                    try:
                        result: dict[str, object] = dict(
                            importer(
                                connection,
                                resolved_account_id,
                                filename,
                                content,
                                allow_reconciled=allow_reconciled,
                            )
                        )
                    except ReconciledPeriodChange as change:
                        return jsonify(
                            {
                                "error": f"{filename}: {change}",
                                "confirm_reconciled": True,
                                "account_id": change.account_id,
                                "reconciled_through": change.reconciled_through,
                                "transaction_count": change.transaction_count,
                                "files_imported": len(results),
                            }
                        ), 409
                    TransactionService(connection).recalculate_balances(resolved_account_id)
                    result["reconciled_periods_needing_review"] = [
                        _checkpoint_json(checkpoint)
                        for checkpoint in ReconciliationCheckpointService(connection).active(
                            resolved_account_id
                        )
                        if checkpoint.status == checkpoint.NEEDS_REVIEW
                    ]
                    results.append(result)
                except (TypeError, ValueError, sqlite3.IntegrityError, UnicodeDecodeError) as error:
                    raise ValueError(f"{item.filename}: {error}") from error
        return jsonify(
            {
                "files": len(results),
                "imported": sum(int(str(item["imported"])) for item in results),
                "duplicates": sum(int(str(item["duplicates"])) for item in results),
                "results": results,
            }
        ), 201
    except (TypeError, ValueError, sqlite3.IntegrityError, UnicodeDecodeError) as error:
        return jsonify(
            {"error": str(error), "help_url": "/transactions#transaction-import-help"}
        ), 400


@blueprint.get("/api/model/transactions")
def model_transactions():
    account_id = request.args.get("account_id", type=int)
    account_type = request.args.get("account_type")
    with dependency("connect")() as connection:
        return jsonify(
            {
                "transactions": TransactionService(connection).summary(account_id, account_type),
                "opening_balances": TransactionService(connection).opening_balances(
                    account_id, account_type
                ),
            }
        )


def _checkpoint_json(checkpoint: ReconciliationCheckpoint) -> dict[str, object]:
    return {
        "id": checkpoint.id,
        "period_start": checkpoint.period_start,
        "reconciled_through": checkpoint.reconciled_through,
        "closing_balance": checkpoint.closing_balance,
        "transaction_count": checkpoint.transaction_count,
        "source": checkpoint.source,
        "status": checkpoint.status,
        "difference": checkpoint.difference,
    }


@blueprint.get("/api/model/accounts/<int:account_id>/reconciliation")
def account_reconciliation_route(account_id: int):
    with dependency("connect")() as connection:
        service = ReconciliationCheckpointService(connection)
        checkpoints = service.active(account_id)
        return jsonify(
            {
                "account_id": account_id,
                "reconciled_through": service.locked_through(account_id),
                "needs_review": any(item.status == item.NEEDS_REVIEW for item in checkpoints),
                "checkpoints": [_checkpoint_json(item) for item in checkpoints],
            }
        )


@blueprint.post("/api/model/accounts/<int:account_id>/reconcile")
def reconcile_account_route(account_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            result = TransactionService(connection).reconcile(
                account_id, str(payload["date"]), as_decimal(payload["amount"])
            )
        return jsonify(result), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400
