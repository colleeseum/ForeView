from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from decimal import Decimal

import pytest
from flask import Flask

from domain.annual_tax_value import AnnualTaxValue
from domain.parsed_tax_value import ParsedTaxValue
from domain.resolved_income_source import ResolvedIncomeSource
from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.annual_tax_value_repository import AnnualTaxValueRepository
from repositories.correction_repository import (
    CorrectionConflictError,
    CorrectionRepository,
)
from services.database_initialization import ensure_domain_schema
from services.income_tax_snapshot_service import IncomeTaxSnapshotService
from services.income_tax_source_resolver import source_fingerprint
from web.correction_routes import blueprint as correction_blueprint
from web.income_routes import blueprint as income_blueprint


@pytest.fixture
def database() -> Iterator[sqlite3.Connection]:
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    ensure_domain_schema(database)
    database.execute("INSERT INTO people(id, name) VALUES (1, 'Example Person')")
    yield database
    database.close()


def source_value(amount: str = "100000") -> AnnualTaxValue:
    return AnnualTaxValue(
        id=10,
        person_id=1,
        tax_year=2025,
        effective_year=2025,
        document_kind="return",
        jurisdiction="CA",
        concept="employment_income",
        description="Employment income",
        reported_amount=Decimal(amount),
        determined_amount=None,
        line_code="10100",
        source="UFile T1",
        source_version="2026.09.29",
        document_hash="document-hash",
    )


def resolved_source(amount: str = "100000") -> ResolvedIncomeSource:
    value = source_value(amount)
    return ResolvedIncomeSource(
        id=value.id,
        concept=value.concept,
        description=value.description,
        document_kind=value.document_kind,
        jurisdiction=value.jurisdiction,
        reported_amount=value.reported_amount,
        determined_amount=value.determined_amount,
        line_code=value.line_code,
        source=value.source,
        source_version=value.source_version,
        document_hash=value.document_hash,
    )


def test_correction_lifecycle_appends_immutable_revisions(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    source = resolved_source()

    created = repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Corrected from supporting records",
        source,
        "fingerprint",
    )
    edited = repository.edit(
        1,
        2025,
        "employment_income",
        Decimal("115000"),
        "Updated after review",
        expected_revision=1,
    )
    confirmed = repository.confirm(
        1,
        2025,
        "employment_income",
        source,
        "confirmed-fingerprint",
        expected_revision=2,
    )
    removed = repository.remove(
        1,
        2025,
        "employment_income",
        expected_revision=3,
    )

    history = repository.get_history(1, 2025, "employment_income")
    assert [item.revision_number for item in history] == [1, 2, 3, 4]
    assert [item.revision_kind for item in history] == [
        "create",
        "edit",
        "confirm",
        "remove",
    ]
    assert history[0].correct_amount == Decimal("110000")
    assert history[1].correct_amount == Decimal("115000")
    assert created.id != edited.id != confirmed.id != removed.id
    assert repository.get(1, 2025, "employment_income") is None


def test_stale_edit_is_rejected_without_appending_revision(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        resolved_source(),
        "fingerprint",
    )
    repository.edit(
        1,
        2025,
        "employment_income",
        Decimal("115000"),
        "Current correction",
        expected_revision=1,
    )

    with pytest.raises(CorrectionConflictError, match="stale"):
        repository.edit(
            1,
            2025,
            "employment_income",
            Decimal("120000"),
            "Stale correction",
            expected_revision=1,
        )

    history = repository.get_history(1, 2025, "employment_income")
    assert len(history) == 2
    assert history[-1].correct_amount == Decimal("115000")


def test_edit_preserves_fingerprint_and_confirmation_refreshes_source(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    original_source = resolved_source("100000")
    original_fingerprint = source_fingerprint(original_source)
    repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        original_source,
        original_fingerprint,
    )

    edited = repository.edit(
        1,
        2025,
        "employment_income",
        Decimal("115000"),
        "Amount changed without reviewing source",
        expected_revision=1,
    )

    assert edited.fingerprint == original_fingerprint
    assert edited.source_reported_amount == Decimal("100000")

    current_source = resolved_source("102000")
    current_fingerprint = source_fingerprint(current_source)
    confirmed = repository.confirm(
        1,
        2025,
        "employment_income",
        current_source,
        current_fingerprint,
        expected_revision=2,
    )

    assert confirmed.fingerprint == current_fingerprint
    assert confirmed.source_reported_amount == Decimal("102000")
    assert repository.get_history(1, 2025, "employment_income")[0].fingerprint == (
        original_fingerprint
    )


def test_repeated_remove_is_idempotent(database: sqlite3.Connection) -> None:
    repository = CorrectionRepository(database)
    repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        resolved_source(),
        "fingerprint",
    )
    removed = repository.remove(
        1,
        2025,
        "employment_income",
        expected_revision=1,
    )

    repeated = repository.remove(
        1,
        2025,
        "employment_income",
        expected_revision=1,
    )

    assert repeated.id == removed.id
    assert len(repository.get_history(1, 2025, "employment_income")) == 2


def test_removed_correction_can_be_reactivated_as_a_new_revision(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        resolved_source(),
        "initial-fingerprint",
    )
    repository.remove(1, 2025, "employment_income", expected_revision=1)

    reactivated = repository.create(
        1,
        2025,
        "employment_income",
        Decimal("112000"),
        "New evidence supports another correction",
        resolved_source("101000"),
        "new-fingerprint",
        expected_revision=2,
    )

    assert reactivated.revision_number == 3
    assert reactivated.revision_kind == "create"
    assert reactivated.correct_amount == Decimal("112000")
    assert repository.get(1, 2025, "employment_income") == reactivated


def test_snapshot_uses_latest_active_revision_and_ignores_tombstone(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    source = source_value()
    correction_source = resolved_source()
    repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        correction_source,
        "fingerprint",
    )
    repository.edit(
        1,
        2025,
        "employment_income",
        Decimal("115000"),
        "Current correction",
        expected_revision=1,
    )
    service = IncomeTaxSnapshotService(repository)

    corrected = service.build([], [], [source], person_id=1, year=2025)

    assert corrected is not None
    corrected_value = next(
        value for value in corrected.values if value.concept == "employment_income"
    )
    assert corrected_value.amount == Decimal("115000")
    assert corrected_value.document_kind == "correction"

    repository.remove(
        1,
        2025,
        "employment_income",
        expected_revision=2,
    )
    restored = service.build([], [], [source], person_id=1, year=2025)

    assert restored is not None
    restored_value = next(
        value for value in restored.values if value.concept == "employment_income"
    )
    assert restored_value.amount == Decimal("100000")
    assert restored_value.document_kind == "return"


def test_correction_api_rejects_a_stale_expected_revision(
    database: sqlite3.Connection,
) -> None:
    AnnualTaxValueRepository(database).upsert_value(
        1,
        2025,
        "return",
        "CA",
        "UFile T1",
        "2026.09.29",
        "document-hash",
        ParsedTaxValue(
            concept="employment_income",
            description="Employment income",
            reported_amount=Decimal("100000"),
            line_code="10100",
        ),
    )
    app = Flask(__name__)
    app.register_blueprint(correction_blueprint)
    app.extensions["finance_connect"] = lambda: database
    client = app.test_client()
    created_response = client.post(
        "/api/income/corrections",
        json={
            "person_id": 1,
            "tax_year": 2025,
            "concept": "employment_income",
            "correct_amount": "110000",
            "reason": "Initial correction",
            "expected_revision": 0,
        },
    )
    assert created_response.status_code == 201
    created = created_response.get_json()
    assert created["revision_number"] == 1
    assert created["label"] == "Employment income"

    edited_response = client.put(
        f"/api/income/corrections/{created['id']}",
        json={
            "correct_amount": "115000",
            "reason": "Current correction",
            "expected_revision": 1,
        },
    )
    assert edited_response.status_code == 200
    assert edited_response.get_json()["revision_number"] == 2

    stale_response = client.put(
        f"/api/income/corrections/{created['id']}",
        json={
            "correct_amount": "120000",
            "reason": "Stale correction",
            "expected_revision": 1,
        },
    )
    assert stale_response.status_code == 409
    assert len(CorrectionRepository(database).get_history(1, 2025, "employment_income")) == 2


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"concept": "unknown"}, "Unsupported income and tax concept"),
        ({"correct_amount": "NaN"}, "Invalid amount"),
        ({"correct_amount": "Infinity"}, "Invalid amount"),
        ({"correct_amount": "-0.01"}, "cannot be negative"),
        ({"reason": "  "}, "Correction reason is required"),
        ({"tax_year": 1899}, "Tax year must be between"),
    ],
)
def test_correction_api_rejects_invalid_input_without_writing(
    database: sqlite3.Connection,
    changes: dict[str, object],
    message: str,
) -> None:
    AnnualTaxValueRepository(database).upsert_value(
        1,
        2025,
        "return",
        "CA",
        "UFile T1",
        "2026.09.29",
        "document-hash",
        ParsedTaxValue(
            concept="employment_income",
            description="Employment income",
            reported_amount=Decimal("100000"),
            line_code="10100",
        ),
    )
    app = Flask(__name__)
    app.register_blueprint(correction_blueprint)
    app.extensions["finance_connect"] = lambda: database
    payload: dict[str, object] = {
        "person_id": 1,
        "tax_year": 2025,
        "concept": "employment_income",
        "correct_amount": "110000",
        "reason": "Supporting records differ",
        "expected_revision": 0,
    }
    payload.update(changes)

    response = app.test_client().post("/api/income/corrections", json=payload)

    assert response.status_code == 400
    assert message in response.get_json()["error"]
    assert CorrectionRepository(database).get_history(1, 2025, "employment_income") == []


def test_correction_api_rejects_invalid_edit_without_appending_revision(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    created = repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        resolved_source(),
        "fingerprint",
    )
    database.commit()
    app = Flask(__name__)
    app.register_blueprint(correction_blueprint)
    app.extensions["finance_connect"] = lambda: database

    response = app.test_client().put(
        f"/api/income/corrections/{created.id}",
        json={
            "correct_amount": "-1",
            "reason": "Invalid negative correction",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 400
    assert len(repository.get_history(1, 2025, "employment_income")) == 1


def test_correction_api_derives_review_status_and_confirmation_refreshes_source(
    database: sqlite3.Connection,
) -> None:
    tax_values = AnnualTaxValueRepository(database)
    tax_values.upsert_value(
        1,
        2025,
        "return",
        "CA",
        "UFile T1",
        "2026.09.29",
        "document-hash",
        ParsedTaxValue(
            concept="employment_income",
            description="Employment income",
            reported_amount=Decimal("100000"),
            line_code="10100",
        ),
    )
    app = Flask(__name__)
    app.register_blueprint(correction_blueprint)
    app.extensions["finance_connect"] = lambda: database
    client = app.test_client()
    created_response = client.post(
        "/api/income/corrections",
        json={
            "person_id": 1,
            "tax_year": 2025,
            "concept": "employment_income",
            "correct_amount": "110000",
            "reason": "Supporting records differ",
            "expected_revision": 0,
        },
    )
    created = created_response.get_json()
    assert created_response.status_code == 201
    assert created["review_required"] is False
    assert created["source_at_correction"]["amount"] == "100000.00"

    unchanged = client.get("/api/income/corrections/person/1/year/2025").get_json()["corrections"][
        0
    ]
    assert unchanged["review_required"] is False

    tax_values.upsert_value(
        1,
        2025,
        "return",
        "CA",
        "UFile T1",
        "2026.09.29",
        "document-hash",
        ParsedTaxValue(
            concept="employment_income",
            description="Employment income",
            reported_amount=Decimal("102000"),
            line_code="10100",
        ),
    )
    changed = client.get("/api/income/corrections/person/1/year/2025").get_json()["corrections"][0]
    assert changed["review_required"] is True
    assert changed["current_underlying"]["amount"] == "102000.00"

    edited_response = client.put(
        f"/api/income/corrections/{created['id']}",
        json={
            "correct_amount": "111000",
            "reason": "Correction edited without source review",
            "expected_revision": 1,
        },
    )
    edited = edited_response.get_json()
    assert edited["review_required"] is True
    assert edited["source_at_correction"]["amount"] == "100000.00"

    confirmed_response = client.post(
        f"/api/income/corrections/{edited['id']}/confirm",
        json={"expected_revision": 2},
    )
    confirmed = confirmed_response.get_json()
    assert confirmed_response.status_code == 200
    assert confirmed["revision_number"] == 3
    assert confirmed["review_required"] is False
    assert confirmed["source_at_correction"]["amount"] == "102000.00"

    tax_values.replace_document(
        1,
        2025,
        "return",
        "CA",
        "UFile T1",
        "2026.09.29",
        "document-hash",
        [],
    )
    disappeared = client.get("/api/income/corrections/person/1/year/2025").get_json()[
        "corrections"
    ][0]
    assert disappeared["review_required"] is True
    assert disappeared["current_underlying"]["amount"] is None


def test_correction_api_accepts_annual_record_fallback(
    database: sqlite3.Connection,
) -> None:
    AnnualEmploymentActualRepository(database).upsert(
        1,
        2025,
        Decimal("90000"),
        province_of_residence="QC",
        source="Manual annual record",
    )
    app = Flask(__name__)
    app.register_blueprint(correction_blueprint)
    app.register_blueprint(income_blueprint)
    app.extensions["finance_connect"] = lambda: database
    response = app.test_client().post(
        "/api/income/corrections",
        json={
            "person_id": 1,
            "tax_year": 2025,
            "concept": "employment_income",
            "correct_amount": "91000",
            "reason": "Supporting records differ",
            "expected_revision": 0,
        },
    )

    assert response.status_code == 201
    correction = response.get_json()
    assert correction["source_at_correction"]["amount"] == "90000.00"
    assert correction["source_at_correction"]["document_kind"] == "annual_record"

    income = app.test_client().get("/api/income?person_id=1").get_json()
    assert income["snapshot"]["values"][0]["amount"] == "91000.00"
    assert income["corrections"] == [correction]
