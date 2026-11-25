# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from hashlib import sha256
from typing import Any

import pytest

from domain.money import optional_cents, to_cents
from ingestion.csv_format import parse_csv_transactions
from ingestion.parsing.import_source import ImportSource
from ingestion.parsing.parse_context import ParseContext
from ingestion.parsing.parsed_transaction import ParsedTransaction
from ingestion.parsing.parsed_transaction_document import ParsedTransactionDocument
from ingestion.parsing.parser_identity import ParserIdentity
from ingestion.parsing.transaction_parser import TransactionParser


class SyntheticCsvParser:
    """Exercise the protocol with an existing pure parser, without persistence."""

    identity = ParserIdentity("synthetic.csv", "1")

    def parse(
        self, source: ImportSource, *, context: ParseContext
    ) -> ParsedTransactionDocument | None:
        if not source.filename.endswith(".csv"):
            return None
        rows = parse_csv_transactions(
            source.content,
            institution=context.institution,
            account_number=context.account_number,
            filename=source.filename,
        )
        return ParsedTransactionDocument(
            source=source,
            parser=self.identity,
            rows=tuple(
                ParsedTransaction(
                    row_number=row.row_number,
                    transaction_date=row.transaction_date,
                    amount_cents=to_cents(row.amount),
                    description=row.description,
                    source_balance_cents=optional_cents(row.balance_after),
                    raw_data=row.raw_data,
                )
                for row in rows
            ),
        )


def row(**changes: Any) -> ParsedTransaction:
    return replace(ParsedTransaction(2, "2026-01-20", -1234, '{"Memo": "Épicerie"}'), **changes)


def test_parser_contract_preserves_source_order_occurrences_and_unknown_balances():
    parser: TransactionParser = SyntheticCsvParser()
    source = ImportSource(
        "synthetic.csv",
        "Date,Amount,Description,Balance\n"
        "20260120,-12.34,Épicerie,\n"
        "2026-01-20,-12.34,Épicerie,\n"
        "2026-01-19,0,Crédit,0\n".encode(),
    )
    context = ParseContext("Synthetic", "000001")
    parsed = parser.parse(source, context=context)
    assert parsed is not None
    assert parsed.source is source
    assert parsed.parser == parser.identity
    assert parsed.account_number is None  # A selected-account hint is not source evidence.
    assert [r.row_number for r in parsed.rows] == [2, 3, 4]
    assert [r.transaction_date for r in parsed.rows] == ["2026-01-20", "2026-01-20", "2026-01-19"]
    assert [r.amount_cents for r in parsed.rows] == [-1234, -1234, 0]
    assert [r.source_balance_cents for r in parsed.rows] == [None, None, 0]
    assert [r.description for r in parsed.rows] == ["Épicerie", "Épicerie", "Crédit"]
    assert '"Balance": ""' in parsed.rows[0].raw_data
    assert '"Balance": "0"' in parsed.rows[2].raw_data


def test_unrecognized_input_and_malformed_recognized_input_are_distinct():
    parser: TransactionParser = SyntheticCsvParser()
    assert parser.parse(ImportSource("statement.pdf", b"unknown"), context=ParseContext()) is None
    with pytest.raises(ValueError, match="Unrecognized CSV format"):
        parser.parse(ImportSource("statement.csv", b"Unsupported\nvalue"), context=ParseContext())


def test_source_identity_uses_original_bytes_and_separate_filename():
    source = ImportSource("first.csv", b"Date,Amount\n2026-01-01,1.00\n")
    renamed = replace(source, filename="second.csv")
    assert source.content_hash == sha256(source.content).hexdigest()
    assert source.content_hash == renamed.content_hash
    assert source != renamed
    assert replace(source, content=source.content + b"\n").content_hash != source.content_hash
    assert ImportSource("empty.csv", b"").content_hash == sha256(b"").hexdigest()


@pytest.mark.parametrize("filename", ["", "  ", None, 123])
def test_source_rejects_missing_filename(filename):
    with pytest.raises(ValueError):
        ImportSource(filename, b"")


@pytest.mark.parametrize("content", [bytearray(b"mutable"), memoryview(b"data"), "text", 12])
def test_source_requires_immutable_bytes(content):
    with pytest.raises(TypeError):
        ImportSource("synthetic.csv", content)


@pytest.mark.parametrize("key,version", [("", "1"), ("csv", " "), (None, "1"), ("csv", 1)])
def test_parser_identity_requires_both_key_and_version(key, version):
    with pytest.raises(ValueError):
        ParserIdentity(key, version)


@pytest.mark.parametrize("field", ["institution", "account_number"])
def test_context_rejects_mutable_hints(field):
    with pytest.raises(TypeError):
        ParseContext(**{field: []})


@pytest.mark.parametrize(
    "value,expected",
    [("20260120", "2026-01-20"), ("2026-W04-2", "2026-01-20"), ("2026-01-20", "2026-01-20")],
)
def test_dates_are_canonical_without_changing_raw_evidence(value, expected):
    parsed = row(transaction_date=value)
    assert parsed.transaction_date == expected
    assert parsed.raw_data == '{"Memo": "Épicerie"}'


@pytest.mark.parametrize("value", ["2026-02-30", "01/20/2026", "2026-01-20T12:00:00", ""])
def test_adapter_must_supply_a_valid_iso_date(value):
    with pytest.raises(ValueError):
        row(transaction_date=value)


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"row_number": 0}, ValueError),
        ({"row_number": True}, ValueError),
        ({"row_number": 1.5}, ValueError),
        ({"amount_cents": 1.25}, TypeError),
        ({"amount_cents": Decimal("1")}, TypeError),
        ({"amount_cents": True}, TypeError),
        ({"source_balance_cents": False}, TypeError),
        ({"source_balance_cents": "0"}, TypeError),
        ({"transaction_date": 20260120}, TypeError),
        ({"raw_data": {}}, TypeError),
        ({"transaction_type": []}, TypeError),
        ({"description": []}, TypeError),
        ({"category": {}}, TypeError),
    ],
)
def test_transaction_rejects_lossy_or_mutable_values(changes, error):
    with pytest.raises(error):
        row(**changes)


def test_document_owns_an_immutable_row_sequence_without_deduplication():
    first = row()
    rows = [first, first]
    document = ParsedTransactionDocument(
        ImportSource("synthetic.csv", b""),
        ParserIdentity("csv", "1"),
        rows,  # type: ignore[arg-type]
    )
    rows.clear()
    assert document.rows == (first, first)
    assert replace(document, rows=()).rows == ()
    assert replace(document, account_number="000001").account_number == "000001"


@pytest.mark.parametrize(
    "changes",
    [{"source": b""}, {"parser": "csv"}, {"rows": ({},)}, {"account_number": []}],
)
def test_document_rejects_untyped_or_mutable_nested_values(changes):
    with pytest.raises(TypeError):
        replace(
            ParsedTransactionDocument(
                ImportSource("synthetic.csv", b""), ParserIdentity("csv", "1"), ()
            ),
            **changes,
        )


def test_values_are_frozen_and_default_repr_omits_private_source_text():
    source = ImportSource("private-file.csv", b"private document text")
    context = ParseContext("Synthetic", "private-account")
    identity = ParserIdentity("csv", "1")
    transaction = row(description="private description")
    document = ParsedTransactionDocument(source, identity, (transaction,), "private-account")
    for value, field, replacement in (
        (source, "content", b"changed"),
        (context, "account_number", "changed"),
        (identity, "version", "changed"),
        (transaction, "amount_cents", 0),
        (document, "rows", ()),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, replacement)
    assert "private" not in repr((source, context, transaction, document))
    assert "Épicerie" not in repr(transaction)
