from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from decimal import Decimal

import pytest
from flask import Flask

from domain.annual_tax_value import AnnualTaxValue
from domain.parsed_tax_value import ParsedTaxValue
from repositories.annual_tax_value_repository import AnnualTaxValueRepository
from repositories.correction_repository import (
    CorrectionConflictError,
    CorrectionRepository,
)
from services.database_initialization import ensure_domain_schema
from services.income_tax_snapshot_service import IncomeTaxSnapshotService
from web.correction_routes import blueprint as correction_blueprint


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


def test_correction_lifecycle_appends_immutable_revisions(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    source = source_value()

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
        source_value(),
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


def test_repeated_remove_is_idempotent(database: sqlite3.Connection) -> None:
    repository = CorrectionRepository(database)
    repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        source_value(),
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


def test_snapshot_uses_latest_active_revision_and_ignores_tombstone(
    database: sqlite3.Connection,
) -> None:
    repository = CorrectionRepository(database)
    source = source_value()
    repository.create(
        1,
        2025,
        "employment_income",
        Decimal("110000"),
        "Initial correction",
        source,
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
