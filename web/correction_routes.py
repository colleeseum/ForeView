from __future__ import annotations

import sqlite3
from decimal import Decimal
from hashlib import sha256
from typing import Any

from flask import Blueprint, jsonify, request

from domain.annual_tax_value import AnnualTaxValue
from domain.factual_correction_revision import FactualCorrectionRevision
from repositories.annual_tax_value_repository import AnnualTaxValueRepository
from repositories.correction_repository import (
    CorrectionConflictError,
    CorrectionNotFoundError,
    CorrectionRepository,
)
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
            source = _find_source_value(
                AnnualTaxValueRepository(connection).list_for_person(person_id),
                tax_year,
                concept,
            )
            if source is None:
                return jsonify({"error": "No source value exists for this correction"}), 400
            revision = CorrectionRepository(connection).create(
                person_id,
                tax_year,
                concept,
                amount,
                reason,
                source,
                _compute_fingerprint(source),
                expected_revision=expected_revision,
            )
        return jsonify(_revision_json(revision)), 201
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
        return jsonify(_revision_json(revision))
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
            revision = repository.confirm(
                target.person_id,
                target.tax_year,
                target.concept,
                expected_revision=expected_revision,
            )
        return jsonify(_revision_json(revision))
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
        return jsonify(_revision_json(revision))
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
    return jsonify({"corrections": [_revision_json(item) for item in revisions]})


@blueprint.get("/api/income/corrections/person/<int:person_id>/year/<int:tax_year>")
def list_corrections_for_year(person_id: int, tax_year: int):
    with dependency("connect")() as connection:
        revisions = CorrectionRepository(connection).list_for_year(person_id, tax_year)
    return jsonify({"corrections": [_revision_json(item) for item in revisions]})


@blueprint.get("/api/income/corrections/person/<int:person_id>/year/<int:tax_year>/<concept>")
def correction_history(person_id: int, tax_year: int, concept: str):
    with dependency("connect")() as connection:
        revisions = CorrectionRepository(connection).get_history(person_id, tax_year, concept)
    return jsonify({"corrections": [_revision_json(item) for item in revisions]})


def _target(repository: CorrectionRepository, revision_id: int) -> FactualCorrectionRevision:
    target = repository.get_by_id(revision_id)
    if target is None:
        raise CorrectionNotFoundError("Correction revision does not exist")
    return target


def _find_source_value(
    tax_values: list[AnnualTaxValue], tax_year: int, concept: str
) -> AnnualTaxValue | None:
    matches = [
        value
        for value in tax_values
        if value.tax_year == tax_year
        and value.effective_year == tax_year
        and value.concept == concept
    ]
    return matches[0] if matches else None


def _compute_fingerprint(source: AnnualTaxValue) -> str:
    data = "|".join(
        (
            source.document_kind,
            source.jurisdiction,
            source.concept,
            source.source_version,
            source.document_hash,
        )
    )
    return sha256(data.encode()).hexdigest()


def _revision_json(revision: FactualCorrectionRevision) -> dict[str, Any]:
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
    }
