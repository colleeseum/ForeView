# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import sqlite3
from contextlib import closing, contextmanager
from dataclasses import FrozenInstanceError, replace

import pytest

from domain.reconciliation_checkpoint import ReconciliationCheckpoint
from domain.validation_error import ValidationError
from ingestion.parsing.generic_csv_parser import GenericCsvParser
from ingestion.parsing.import_source import ImportSource
from ingestion.parsing.parse_context import ParseContext
from repositories.account_repository import AccountRepository
from repositories.csv_analysis_repository import CsvAnalysisRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.reconciliation_checkpoint_repository import ReconciliationCheckpointRepository
from repositories.transaction_repository import TransactionRepository
from services.imports.csv_analysis_service import CsvAnalysisService
from tests.support import create_account, ensure_domain_schema


@contextmanager
def edit(database):
    with closing(sqlite3.connect(database)) as connection, connection:
        yield connection


@pytest.fixture
def model(tmp_path):
    database = tmp_path / "synthetic.sqlite3"
    with edit(database) as connection:
        ensure_domain_schema(connection)
        account = create_account(connection, "Synthetic", "tfsa", account_number="000001")
    return database, account


def document(*rows, header="Date,Amount,Description"):
    source = ImportSource("synthetic.csv", (header + "\n" + "\n".join(rows) + "\n").encode())
    return GenericCsvParser().parse(source, context=ParseContext())


def dump(database):
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        return tuple(connection.iterdump())


def analyse(model, parsed):
    database, account = model
    before = dump(database)
    try:
        return CsvAnalysisService(CsvAnalysisRepository(database)).analyse(account, parsed)
    finally:
        assert dump(database) == before


def checkpoint(connection, account, through, status=ReconciliationCheckpoint.RECONCILED):
    repository = ReconciliationCheckpointRepository(connection)
    result = repository.create(
        account,
        period_start=None,
        reconciled_through=through,
        closing_balance=0,
        net_change=0,
        transaction_count=0,
        source="synthetic",
    )
    if status != result.status:
        repository.set_status(result.id, status, None)
    return result


def test_occurrences_match_starting_ledger_without_collapsing_new_repeats(model):
    database, account = model
    with edit(database) as connection:
        TransactionRepository(connection).create(account, "2026-01-20", 1.23, description="Credit")
    parsed = document(*["2026-01-20,1.23,Credit"] * 3)
    result = analyse(model, parsed)
    assert result.status == "analysed"
    assert (result.new_count, result.duplicate_count, result.reconciled_period_count) == (2, 1, 0)
    assert [r.duplicate for r in result.rows] == [True, False, False]
    assert [r.row for r in result.rows] == list(parsed.rows)
    assert result.locked_through is None


def test_matching_uses_descriptions_and_optional_printed_balances(model):
    database, account = model
    with edit(database) as connection:
        transactions = TransactionRepository(connection)
        transactions.create(account, "2026-01-20", 1, description="Credit", balance_after=0)
        transactions.create(account, "2026-01-20", 1, description="Credit", balance_after=10)
    parsed = document(
        "2026-01-20,1,Credit,0",
        "2026-01-20,1,Credit,5",
        "2026-01-20,1,Credit,",
        "2026-01-20,1,Other,0",
        header="Date,Amount,Description,Balance",
    )
    result = analyse(model, parsed)
    # A missing balance uses the independent base key, just like the legacy matcher.
    assert [r.duplicate for r in result.rows] == [True, False, True, False]
    assert result.duplicate_count == result.new_count == 2


def test_missing_and_empty_descriptions_are_distinct(model):
    database, account = model
    with edit(database) as connection:
        TransactionRepository(connection).create(account, "2026-01-20", 1, description=None)
    missing = analyse(model, document("2026-01-20,1", header="Date,Amount"))
    empty = analyse(model, document("2026-01-20,1,"))
    assert missing.duplicate_count == 1
    assert empty.new_count == 1


@pytest.mark.parametrize("stored_date", ["20260120", "2026-W04-2"])
def test_equivalent_legacy_iso_dates_match_without_rewriting_the_ledger(model, stored_date):
    database, account = model
    with edit(database) as connection:
        TransactionRepository(connection).create(account, stored_date, 1, description="Credit")
    assert analyse(model, document("2026-01-20,1,Credit")).duplicate_count == 1


def test_reading_integer_cent_ledger_does_not_round_through_float_money(model):
    database, account = model
    with edit(database) as connection:
        transaction = TransactionRepository(connection).create(account, "2026-01-20", 1)
        connection.execute(
            "UPDATE transactions SET amount_cents = ?, balance_after_cents = ? WHERE id = ?",
            (100000000000000001, 100000000000000001, transaction.id),
        )
    result = analyse(
        model,
        document(
            "2026-01-20,1000000000000000.01,1000000000000000.01", header="Date,Amount,Balance"
        ),
    )
    assert result.duplicate_count == 1


def test_exact_file_duplicate_retains_original_account_and_imported_row_count(model):
    database, account = model
    parsed = document("2026-01-20,1,Credit", "2026-01-20,1,Credit")
    with edit(database) as connection:
        other = create_account(connection, "Other", "tfsa", account_number="000002")
        batch = ImportBatchRepository(connection).create(
            other, "original.csv", parsed.source.content_hash, row_count=1
        )
        checkpoint(connection, account, "2026-12-31")
    result = analyse(model, parsed)
    assert result.status == "already_imported"
    assert result.existing_batch == batch
    assert result.existing_batch.account_id == other
    assert result.account.id == account
    assert (result.new_count, result.duplicate_count, result.reconciled_period_count) == (0, 1, 0)
    assert result.rows == ()
    assert result.locked_through is None


@pytest.mark.parametrize("through", ["20260131", "2026-W05-6", "2026-01-31"])
def test_only_new_transactions_entering_an_active_lock_need_approval(model, through):
    database, account = model
    with edit(database) as connection:
        checkpoint(connection, account, through, ReconciliationCheckpoint.NEEDS_REVIEW)
        checkpoint(connection, account, "bad-date")
        checkpoint(connection, account, "2027-12-31", ReconciliationCheckpoint.SUPERSEDED)
        TransactionRepository(connection).create(account, "2026-01-20", 1, description="Existing")
    result = analyse(
        model, document("2026-01-20,1,Existing", "2026-01-01,1,New", "2026-02-20,1,Later")
    )
    assert result.locked_through == "2026-01-31"
    assert [r.enters_reconciled_period for r in result.rows] == [False, True, False]
    assert result.reconciled_period_count == 1


def test_only_malformed_or_superseded_checkpoints_do_not_lock_the_account(model):
    database, account = model
    with edit(database) as connection:
        checkpoint(connection, account, "not-a-date")
        checkpoint(connection, account, "2027-12-31", ReconciliationCheckpoint.SUPERSEDED)
    assert analyse(model, document("2026-01-20,1,New")).locked_through is None


@pytest.mark.parametrize("source_account", ["", "---", "000002"])
def test_source_account_mismatch_does_not_change_any_tables(model, source_account):
    with pytest.raises(ValueError, match="does not match"):
        analyse(model, replace(document("2026-01-20,1,Credit"), account_number=source_account))


def test_formatted_source_account_matches_the_selected_account(model):
    result = analyse(model, replace(document("2026-01-20,1,Credit"), account_number="000-001"))
    assert result.new_count == 1


def test_unknown_account_is_rejected_and_missing_database_is_not_created(model, tmp_path):
    database, _ = model
    with pytest.raises(ValidationError, match="Account not found"):
        analyse((database, 99999), document("2026-01-20,1,Credit"))
    absent = tmp_path / "absent.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        CsvAnalysisRepository(absent).read(1, "missing")
    assert not absent.exists()


def test_empty_document_and_result_values_remain_immutable(model):
    result = analyse(model, document())
    assert result.status == "analysed"
    assert (result.new_count, result.duplicate_count, result.reconciled_period_count) == (0, 0, 0)
    with pytest.raises(FrozenInstanceError):
        result.locked_through = "2026-01-01"
    populated = analyse(model, document("2026-01-20,1,Credit"))
    with pytest.raises(FrozenInstanceError):
        populated.rows[0].duplicate = True


def test_snapshot_connection_is_read_only_and_closed_even_on_errors(model, monkeypatch):
    database, account = model
    original_connect = sqlite3.connect
    connections = []

    def connect(database_uri, **kwargs):
        assert database_uri.endswith("?mode=ro") and kwargs["uri"] is True
        connection = original_connect(database_uri, **kwargs)
        connections.append(connection)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("CREATE TABLE forbidden(value TEXT)")
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    CsvAnalysisRepository(database).read(account, "missing")
    with pytest.raises(ValidationError):
        CsvAnalysisRepository(database).read(99999, "missing")
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_account_batch_ledger_and_checkpoints_share_one_read_snapshot(model, monkeypatch):
    database, account = model
    parsed = document("2026-01-20,1,Credit")
    with edit(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    original_get = AccountRepository.get

    def read_then_change(self, account_id):
        result = original_get(self, account_id)  # Establish the SQLite read snapshot.
        with edit(database) as writer:
            TransactionRepository(writer).create(account, "2026-01-20", 1, description="Credit")
            checkpoint(writer, account, "2026-01-31")
            ImportBatchRepository(writer).create(
                account, "concurrent.csv", parsed.source.content_hash
            )
        return result

    monkeypatch.setattr(AccountRepository, "get", read_then_change)
    state = CsvAnalysisRepository(database).read(account, parsed.source.content_hash)
    assert state.ledger == () and state.checkpoints == () and state.existing_batch is None
    monkeypatch.setattr(AccountRepository, "get", original_get)
    current = CsvAnalysisRepository(database).read(account, parsed.source.content_hash)
    assert len(current.ledger) == len(current.checkpoints) == 1
    assert current.existing_batch is not None
