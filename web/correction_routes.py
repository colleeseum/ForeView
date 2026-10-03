from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request

from domain.factual_correction_revision import FactualCorrectionRevision
from domain.resolved_income_source import ResolvedIncomeSource
from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.annual_tax_assessment_repository import AnnualTaxAssessmentRepository
from repositories.annual_tax_value_repository import AnnualTaxValueRepository
from repositories.correction_repository import (
    CorrectionConflictError,
    CorrectionNotFoundError,
    CorrectionRepository,
)
from services.income_tax_source_resolver import IncomeTaxSourceResolver, source_fingerprint
from web.dependencies import dependency

blueprint = Blueprint("corrections", __name__)


@blueprint.post("/api/income/corrections")
def create_correction():
    payload = request.get_json(silent=True) or {}
    try:
        person_id = int(payload["person_id"])
        tax_year = int(payload["tax_year"])
        concept = str(payload["concept"])
        amount = Decimal(str(payload["correct_amount"]))
        reason = str(payload["reason"])
        expected_revision = int(payload.get("expected_revision", 0))
        with dependency("connect")() as connection:
            source = _resolver(connection, person_id).resolve(tax_year, concept)
            if not source.has_value:
                return jsonify({"error": "No source value exists for this correction"}), 400
            revision = CorrectionRepository(connection).create(
                person_id,
                tax_year,
                concept,
                amount,
                reason,
                source,
                source_fingerprint(source),
                expected_revision=expected_revision,
            )
        return jsonify(_revision_json(revision, source)), 201
    except CorrectionConflictError as error:
        return jsonify({"error": str(error)}), 409
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put("/api/income/corrections/<int:revision_id>")
def edit_correction(revision_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(payload["correct_amount"]))
        reason = str(payload["reason"])
        expected_revision = int(payload["expected_revision"])
        with dependency("connect")() as connection:
            repository = CorrectionRepository(connection)
            target = _target(repository, revision_id)
            revision = repository.edit(
                target.person_id,
                target.tax_year,
                target.concept,
                amount,
                reason,
                expected_revision=expected_revision,
            )
            source = _resolver(connection, target.person_id).resolve(
                target.tax_year, target.concept
            )
        return jsonify(_revision_json(revision, source))
    except CorrectionConflictError as error:
        return jsonify({"error": str(error)}), 409
    except CorrectionNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/income/corrections/<int:revision_id>/confirm")
def confirm_correction(revision_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        expected_revision = int(payload["expected_revision"])
        with dependency("connect")() as connection:
            repository = CorrectionRepository(connection)
            target = _target(repository, revision_id)
            source = _resolver(connection, target.person_id).resolve(
                target.tax_year, target.concept
            )
            revision = repository.confirm(
                target.person_id,
                target.tax_year,
                target.concept,
                source,
                source_fingerprint(source),
                expected_revision=expected_revision,
            )
        return jsonify(_revision_json(revision, source))
    except CorrectionConflictError as error:
        return jsonify({"error": str(error)}), 409
    except CorrectionNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.delete("/api/income/corrections/<int:revision_id>")
def remove_correction(revision_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        expected_revision = int(payload["expected_revision"])
        with dependency("connect")() as connection:
            repository = CorrectionRepository(connection)
            target = _target(repository, revision_id)
            revision = repository.remove(
                target.person_id,
                target.tax_year,
                target.concept,
                expected_revision=expected_revision,
            )
            source = _resolver(connection, target.person_id).resolve(
                target.tax_year, target.concept
            )
        return jsonify(_revision_json(revision, source))
    except CorrectionConflictError as error:
        return jsonify({"error": str(error)}), 409
    except CorrectionNotFoundError as error:
        return jsonify({"error": str(error)}), 404
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.get("/api/income/corrections/person/<int:person_id>")
def list_corrections(person_id: int):
    with dependency("connect")() as connection:
        revisions = CorrectionRepository(connection).list_for_person(person_id)
        resolver = _resolver(connection, person_id)
        result = [
            _revision_json(revision, resolver.resolve(revision.tax_year, revision.concept))
            for revision in revisions
        ]
    return jsonify({"corrections": result})


@blueprint.get("/api/income/corrections/person/<int:person_id>/year/<int:tax_year>")
def list_corrections_for_year(person_id: int, tax_year: int):
    with dependency("connect")() as connection:
        revisions = CorrectionRepository(connection).list_for_year(person_id, tax_year)
        resolver = _resolver(connection, person_id)
        result = [
            _revision_json(revision, resolver.resolve(tax_year, revision.concept))
            for revision in revisions
        ]
    return jsonify({"corrections": result})


@blueprint.get("/api/income/corrections/person/<int:person_id>/year/<int:tax_year>/<concept>")
def correction_history(person_id: int, tax_year: int, concept: str):
    with dependency("connect")() as connection:
        revisions = CorrectionRepository(connection).get_history(person_id, tax_year, concept)
        source = _resolver(connection, person_id).resolve(tax_year, concept)
    return jsonify({"corrections": [_revision_json(revision, source) for revision in revisions]})


def _target(repository: CorrectionRepository, revision_id: int) -> FactualCorrectionRevision:
    target = repository.get_by_id(revision_id)
    if target is None:
        raise CorrectionNotFoundError("Correction revision does not exist")
    return target


def _resolver(connection: sqlite3.Connection, person_id: int) -> IncomeTaxSourceResolver:
    return IncomeTaxSourceResolver(
        AnnualEmploymentActualRepository(connection).list_for_person(person_id),
        AnnualTaxAssessmentRepository(connection).list_for_person(person_id),
        AnnualTaxValueRepository(connection).list_for_person(person_id),
    )


def _revision_json(
    revision: FactualCorrectionRevision, current_source: ResolvedIncomeSource
) -> dict[str, Any]:
    source_amount = (
        revision.source_determined_amount
        if revision.source_determined_amount is not None
        else revision.source_reported_amount
    )
    return {
        "id": revision.id,
        "person_id": revision.person_id,
        "tax_year": revision.tax_year,
        "concept": revision.concept,
        "revision_number": revision.revision_number,
        "revision_kind": revision.revision_kind,
        "correct_amount": str(revision.correct_amount)
        if revision.correct_amount is not None
        else None,
        "reason": revision.reason,
        "created_at": revision.created_at,
        "review_required": (
            revision.is_active and revision.fingerprint != source_fingerprint(current_source)
        ),
        "source_at_correction": {
            "amount": str(source_amount) if source_amount is not None else None,
            "document_kind": revision.source_document_kind,
            "jurisdiction": revision.source_jurisdiction,
            "line_code": revision.source_line_code,
            "source": revision.source_name,
            "source_version": revision.source_version,
            "document_hash": revision.source_document_hash,
        },
        "current_underlying": _source_json(current_source),
    }


def _source_json(source: ResolvedIncomeSource) -> dict[str, Any]:
    return {
        "amount": str(source.amount) if source.amount is not None else None,
        "document_kind": source.document_kind,
        "jurisdiction": source.jurisdiction,
        "line_code": source.line_code,
        "source": source.source,
        "source_version": source.source_version,
        "document_hash": source.document_hash,
    }
