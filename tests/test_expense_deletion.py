# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Deletion integrity against the production migration chain and synthetic facts."""

import sqlite3
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from domain.validation_error import ValidationError
from domain.validation_lookup_error import ValidationLookupError
from repositories.expense_repository import ExpenseRepository
from repositories.import_batch_repository import ImportBatchRepository
from services.expenses.expense_service import ExpenseService
from services.runtime.database_initialization import ensure_domain_schema
from tests.support import create_account


@pytest.fixture
def env():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    ensure_domain_schema(connection)
    repository = ExpenseRepository(connection)
    category = repository.create_category("Synthetic utilities", "required")
    connection.commit()
    yield SimpleNamespace(
        connection=connection,
        repository=repository,
        category=category,
        batches=ImportBatchRepository(connection),
        service=ExpenseService(connection),
    )
    connection.close()


def imported(
    env, *, name="Synthetic Hydro", source_hash="synthetic-a", start="2026-01-01", end="2026-01-31"
):
    batch = env.batches.get_or_create(None, f"{source_hash}.pdf", source_hash, 1)
    record = env.repository.create_imported_expense(
        name=name,
        category_id=env.category.id,
        amount=Decimal("31.00"),
        period_start=date.fromisoformat(start),
        period_end=date.fromisoformat(end),
        source_document_id=batch.id,
        parser_name="synthetic",
        parser_version="2026.10.29",
        period_kind="recurring_statement",
    )
    env.connection.commit()
    return record


def delete(env, record):
    token = ExpenseService.deletion_token(env.repository.get_expense(record.id))
    env.service.delete_expense(record.id, expected_token=token)


def test_duplicate_deletion_preserves_retained_evidence_and_shared_batch(env):
    kept = imported(env)
    duplicate = imported(env)
    assert kept.source_document_id == duplicate.source_document_id
    delete(env, duplicate)
    remaining = env.repository.get_expense(kept.id)
    assert remaining.overlap_status == "clear"
    assert remaining.amount == Decimal("31.00")
    assert remaining.source_hash == kept.source_hash
    assert env.batches.get(kept.source_document_id) is not None
    assert env.repository.totals_for_year(2026)["total"] == Decimal("31.00")
    with pytest.raises(ValidationLookupError):
        env.repository.get_expense(duplicate.id)


@pytest.mark.parametrize("delete_included", [False, True])
def test_resolved_duplicates_preserve_explicit_exclusion_intent(env, delete_included):
    included = imported(env)
    excluded = imported(env)
    env.repository.resolve_overlap(included.id, include=True, note="Keep annual evidence")
    env.repository.resolve_overlap(excluded.id, include=False, note="Loaded twice")
    env.connection.commit()
    delete(env, included if delete_included else excluded)
    remaining = env.repository.get_expense(excluded.id if delete_included else included.id)
    assert remaining.overlap_status == ("resolved_exclude" if delete_included else "clear")
    assert env.repository.totals_for_year(2026)["total"] == Decimal(
        "0.00" if delete_included else "31.00"
    )


def test_last_import_deletes_only_its_orphaned_batch_and_identity(env):
    last = imported(env)
    category_before = env.repository.get_category(env.category.id)
    delete(env, last)
    assert env.repository.list_expenses() == []
    assert env.repository.totals_for_year(2026)["status"] == "missing"
    assert env.batches.get(last.source_document_id) is None
    assert (
        env.connection.execute(
            "SELECT 1 FROM expense_identities WHERE id = ?", (last.identity_id,)
        ).fetchone()
        is None
    )
    assert env.repository.get_category(env.category.id) == category_before


def test_deletion_clears_only_affected_overlaps_and_preserves_genuine_conflicts(env):
    a = imported(env)
    b = imported(env, source_hash="synthetic-b")
    c = imported(env, source_hash="synthetic-c")
    unrelated = imported(env, name="Other utility", source_hash="unrelated")
    env.repository.resolve_overlap(unrelated.id, include=False, note="Intentionally excluded")
    env.connection.commit()
    unrelated_before = env.repository.get_expense(unrelated.id)
    delete(env, b)
    assert env.repository.get_expense(a.id).overlap_status == "potential"
    assert env.repository.get_expense(c.id).overlap_status == "potential"
    assert env.repository.totals_for_year(2026)["status"] == "needs_resolution"
    assert env.repository.get_expense(unrelated.id) == unrelated_before
    delete(env, c)
    assert env.repository.get_expense(a.id).overlap_status == "clear"
    assert env.repository.get_expense(unrelated.id) == unrelated_before


def test_deletion_handles_overlap_chains_and_cross_year_totals(env):
    a = imported(env, start="2025-12-31", end="2026-01-01")
    bridge = imported(env, source_hash="bridge", start="2026-01-01", end="2026-01-15")
    c = imported(env, source_hash="end", start="2026-01-15", end="2026-01-31")
    delete(env, bridge)
    assert env.repository.get_expense(a.id).overlap_status == "clear"
    assert env.repository.get_expense(c.id).overlap_status == "clear"
    assert env.repository.totals_for_year(2025)["total"] == Decimal("15.50")
    assert env.repository.totals_for_year(2026)["total"] == Decimal("46.50")


def test_deletion_refreshes_seasonal_estimate_and_requires_surviving_baseline(env):
    prior = imported(env, source_hash="prior-year", start="2025-01-01", end="2025-12-31")
    current = imported(env)
    # January actuals plus 334 uncovered days of the prior year, adjusted by 2%.
    before = env.repository.totals_for_year(2026)
    assert before["total"] == Decimal("31.00")
    assert before["estimated_total"] == Decimal("59.93")
    duplicate = imported(env)
    assert env.repository.totals_for_year(2026)["status"] == "needs_resolution"
    delete(env, duplicate)
    after = env.repository.totals_for_year(2026)
    assert after["total"] == before["total"]
    assert after["estimated_total"] == before["estimated_total"]
    delete(env, prior)
    without_baseline = env.repository.totals_for_year(2026)
    assert without_baseline["total"] == Decimal("31.00")
    assert without_baseline["estimated_total"] is None
    assert env.repository.get_expense(current.id).overlap_status == "clear"


@pytest.mark.parametrize(
    "consumer", ["raw_transactions", "statement_reconciliations", "future", "future_uppercase"]
)
def test_other_source_consumers_keep_their_shared_batch(env, consumer):
    record = imported(env)
    account = create_account(
        env.connection, "Synthetic bank", "tfsa", account_number="SYN-DELETE-001"
    )
    if consumer == "raw_transactions":
        env.connection.execute(
            "INSERT INTO raw_transactions(batch_id,row_number,row_hash,raw_data) VALUES (?,1,'row','synthetic')",
            (record.source_document_id,),
        )
    elif consumer == "statement_reconciliations":
        env.connection.execute(
            "INSERT INTO statement_reconciliations(account_id,import_batch_id,statement_start,statement_end,status) VALUES (?,?,'2026-01-01','2026-01-31','matched')",
            (account, record.source_document_id),
        )
    else:
        # Even a future cascading consumer must not be removed by metadata cleanup.
        target = "IMPORT_BATCHES" if consumer == "future_uppercase" else "import_batches"
        env.connection.execute(
            f'CREATE TABLE "extra source" (batch INTEGER REFERENCES {target}(id) ON DELETE CASCADE)'
        )
        env.connection.execute(
            'INSERT INTO "extra source" VALUES (?)', (record.source_document_id,)
        )
    env.connection.commit()
    delete(env, record)
    assert env.batches.get(record.source_document_id) is not None
    if consumer.startswith("future"):
        assert env.connection.execute('SELECT COUNT(*) FROM "extra source"').fetchone()[0] == 1
    else:
        assert env.connection.execute(f"SELECT COUNT(*) FROM {consumer}").fetchone()[0] == 1


def test_cleanup_failure_rolls_back_record_batch_identity_and_overlap_changes(env):
    a = imported(env)
    b = imported(env, source_hash="other-batch")
    before = env.repository.list_expenses()
    env.connection.execute(
        "CREATE TRIGGER reject_cleanup BEFORE DELETE ON import_batches BEGIN SELECT RAISE(ABORT, 'Synthetic cleanup failure'); END"
    )
    env.connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match="cleanup failure"):
        delete(env, b)
    assert env.repository.list_expenses() == before
    assert env.batches.get(b.source_document_id) is not None
    assert env.batches.get(a.source_document_id) is not None


def test_shared_source_cleanup_quotes_schema_identifiers(env):
    record = imported(env)
    env.connection.execute(
        'CREATE TABLE "extra ""source" ("batch ""id" INTEGER REFERENCES import_batches(id) ON DELETE CASCADE)'
    )
    env.connection.execute('INSERT INTO "extra ""source" VALUES (?)', (record.source_document_id,))
    env.connection.commit()
    delete(env, record)
    assert env.batches.get(record.source_document_id) is not None
    assert env.connection.execute('SELECT COUNT(*) FROM "extra ""source"').fetchone()[0] == 1


def test_stale_token_reused_id_missing_and_manual_deletion(env):
    record = imported(env)
    old_token = ExpenseService.deletion_token(record)
    env.repository.resolve_overlap(record.id, include=False, note="Changed since confirmation")
    env.connection.commit()
    with pytest.raises(ValidationError) as error:
        env.service.delete_expense(record.id, expected_token=old_token)
    assert error.value.code == "expense_delete_stale"
    delete(env, record)
    with pytest.raises(ValidationLookupError):
        env.service.delete_expense(record.id, expected_token=old_token)
    replacement = imported(env, name="Different evidence", source_hash="replacement")
    assert replacement.id == record.id
    with pytest.raises(ValidationError, match="changed"):
        env.service.delete_expense(record.id, expected_token=old_token)
    assert env.repository.get_expense(replacement.id).name == "Different evidence"
    manual = env.repository.create_manual_expense(
        name="Manual evidence",
        category_id=env.category.id,
        amount="10",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    env.connection.commit()
    with pytest.raises(ValidationError) as error:
        env.service.delete_expense(manual.id, expected_token="stale")
    assert error.value.code == "expense_delete_stale"
    assert env.repository.get_expense(manual.id).name == "Manual evidence"
    env.service.delete_expense(manual.id, expected_token=ExpenseService.deletion_token(manual))
    with pytest.raises(ValidationLookupError):
        env.repository.get_expense(manual.id)


def test_batch_cleanup_missing_or_unknown_reference_is_conservative(env):
    assert not env.batches.delete_if_unreferenced(999999)
    record = imported(env)
    env.connection.execute(
        "CREATE TABLE hash_consumer (source TEXT REFERENCES import_batches(file_hash))"
    )
    env.connection.commit()
    delete(env, record)
    assert env.batches.get(record.source_document_id) is not None


def test_deleting_manual_evidence_clears_only_affected_overlap_and_keeps_other_facts(env):
    records = [
        env.repository.create_manual_expense(
            name="Manual utilities",
            category_id=env.category.id,
            amount="10",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        for _ in range(2)
    ]
    unrelated = imported(
        env, name="Other evidence", source_hash="unrelated", start="2026-04-01", end="2026-04-30"
    )
    env.connection.commit()
    assert env.repository.get_expense(records[0].id).overlap_status == "potential"
    current = env.repository.get_expense(records[0].id)
    delete(env, current)
    assert env.repository.get_expense(records[1].id).overlap_status == "clear"
    assert env.repository.get_expense(unrelated.id) == unrelated
    assert env.repository.get_expense(records[1].id).amount == Decimal("10")
