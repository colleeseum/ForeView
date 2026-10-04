# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request

from domain.factual_correction_revision import FactualCorrectionRevision
from domain.income_tax_concept import income_tax_concept
from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.annual_tax_assessment_repository import AnnualTaxAssessmentRepository
from repositories.annual_tax_value_repository import AnnualTaxValueRepository
from repositories.correction_repository import (
    CorrectionConflictError,
    CorrectionNotFoundError,
    CorrectionRepository,
)
from services.factual_correction_validator import FactualCorrectionValidator
from services.income_tax_source_resolver import IncomeTaxSourceResolver, source_fingerprint
from web.correction_serialization import correction_revision_json
from web.dependencies import dependency

blueprint = Blueprint("corrections", __name__)


@blueprint.post("/api/income/corrections")
def create_correction():
    payload = request.get_json(silent=True) or {}
    try:
        values = FactualCorrectionValidator.validate(
            payload["person_id"],
            payload["tax_year"],
            payload["concept"],
            payload["correct_amount"],
            payload["reason"],
        )
        expected_revision = FactualCorrectionValidator.expected_revision(
            payload.get("expected_revision", 0), allow_zero=True
        )
        with dependency("connect")() as connection:
            source = _resolver(connection, values.person_id).resolve(
                values.tax_year, values.concept.key
            )
            if not source.has_value:
                return jsonify({"error": "No source value exists for this correction"}), 400
            revision = CorrectionRepository(connection).create(
                values.person_id,
                values.tax_year,
                values.concept.key,
                values.amount,
                values.reason,
                source,
                source_fingerprint(source),
                expected_revision=expected_revision,
            )
        return jsonify(correction_revision_json(revision, source)), 201
    except CorrectionConflictError as error:
        return jsonify({"error": str(error)}), 409
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put("/api/income/corrections/<int:revision_id>")
def edit_correction(revision_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        expected_revision = FactualCorrectionValidator.expected_revision(
            payload["expected_revision"], allow_zero=False
        )
        with dependency("connect")() as connection:
            repository = CorrectionRepository(connection)
            target = _target(repository, revision_id)
            values = FactualCorrectionValidator.validate(
                target.person_id,
                target.tax_year,
                target.concept,
                payload["correct_amount"],
                payload["reason"],
            )
            revision = repository.edit(
                target.person_id,
                target.tax_year,
                target.concept,
                values.amount,
                values.reason,
                expected_revision=expected_revision,
            )
            source = _resolver(connection, target.person_id).resolve(
                target.tax_year, target.concept
            )
        return jsonify(correction_revision_json(revision, source))
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
        expected_revision = FactualCorrectionValidator.expected_revision(
            payload["expected_revision"], allow_zero=False
        )
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
        return jsonify(correction_revision_json(revision, source))
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
        expected_revision = FactualCorrectionValidator.expected_revision(
            payload["expected_revision"], allow_zero=False
        )
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
        return jsonify(correction_revision_json(revision, source))
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
            correction_revision_json(
                revision, resolver.resolve(revision.tax_year, revision.concept)
            )
            for revision in revisions
        ]
    return jsonify({"corrections": result})


@blueprint.get("/api/income/corrections/person/<int:person_id>/year/<int:tax_year>")
def list_corrections_for_year(person_id: int, tax_year: int):
    with dependency("connect")() as connection:
        revisions = CorrectionRepository(connection).list_for_year(person_id, tax_year)
        resolver = _resolver(connection, person_id)
        result = [
            correction_revision_json(revision, resolver.resolve(tax_year, revision.concept))
            for revision in revisions
        ]
    return jsonify({"corrections": result})


@blueprint.get("/api/income/corrections/person/<int:person_id>/year/<int:tax_year>/<concept>")
def correction_history(person_id: int, tax_year: int, concept: str):
    try:
        definition = income_tax_concept(concept)
        with dependency("connect")() as connection:
            revisions = CorrectionRepository(connection).get_history(
                person_id, tax_year, definition.key
            )
            source = _resolver(connection, person_id).resolve(tax_year, definition.key)
        return jsonify(
            {"corrections": [correction_revision_json(revision, source) for revision in revisions]}
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


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
