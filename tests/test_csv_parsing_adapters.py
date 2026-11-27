# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from decimal import Decimal

import pytest

from domain.money import optional_cents, to_cents
from ingestion.csv_format import CsvTransactionRow, parse_csv_transactions
from ingestion.parsing.csv_evidence import parsed_csv_rows
from ingestion.parsing.generic_csv_parser import GenericCsvParser
from ingestion.parsing.import_source import ImportSource
from ingestion.parsing.parse_context import ParseContext
from ingestion.parsing.transaction_parser import TransactionParser
from institutions.rbc.csv_parser import parse_transactions
from institutions.rbc.transaction_csv_parser import RbcTransactionCsvParser

RBC_HEADER = "Date de l'opération,Numéro du compte,CAD$,Description 1,Description 2\n"


@pytest.mark.parametrize(
    "header,body",
    [
        ("Date,Amount,Description,Balance", '01/20/2026,"($1,234.56)",Épicerie,0'),
        ("Transaction date,Transaction amount,Memo,Running Balance", "2026-01-20,12.34,Crédit,"),
        ("Posted date,Amount,Payee", "20Jan2026,0,Refund"),
        (" Date , Amount , Memo ", "2026-01-20,-1,Repeated"),
    ],
)
def test_generic_parser_preserves_legacy_layout_and_occurrences(header, body):
    source = ImportSource("synthetic.csv", f"{header}\n{body}\n{body}\n".encode("utf-8-sig"))
    context = ParseContext("Synthetic", "000001")
    parser: TransactionParser = GenericCsvParser()
    document = parser.parse(source, context=context)
    assert document is not None
    legacy = parse_csv_transactions(
        source.content,
        institution=context.institution,
        account_number="000001",
        filename=source.filename,
    )
    assert document.source is source
    assert document.parser == parser.identity
    assert document.account_number is None
    assert len(document.rows) == 2
    for new, old in zip(document.rows, legacy, strict=True):
        assert (new.row_number, new.transaction_date, new.description, new.raw_data) == (
            old.row_number,
            old.transaction_date,
            old.description,
            old.raw_data,
        )
        assert new.amount_cents == to_cents(old.amount)
        assert new.source_balance_cents == optional_cents(old.balance_after)


def test_rbc_parser_preserves_source_account_description_and_row_evidence():
    source = ImportSource(
        "synthetic-rbc.csv",
        (RBC_HEADER + "01/20/2026,000-001,-12.34,PAIEMENT,Épicerie\n" * 2).encode("utf-8-sig"),
    )
    parser: TransactionParser = RbcTransactionCsvParser()
    document = parser.parse(source, context=ParseContext("RBC", "000001"))
    legacy = parse_transactions(source.content, "000001", source.filename)
    assert document is not None and legacy is not None
    assert document.parser == parser.identity
    assert document.account_number == "000-001"
    assert len(document.rows) == 2
    assert [r.row_number for r in document.rows] == [2, 3]
    for new, old in zip(document.rows, legacy, strict=True):
        assert new.amount_cents == to_cents(old.amount)
        assert new.description == old.description == "PAIEMENT Épicerie"
        assert new.raw_data == old.raw_data
        assert new.source_balance_cents is None


def test_rbc_unrecognized_format_allows_explicit_generic_fallback():
    source = ImportSource("generic.csv", b"Date,Amount\n2026-01-20,1.25\n")
    context = ParseContext("RBC", "000001")
    assert RbcTransactionCsvParser().parse(source, context=context) is None
    document = GenericCsvParser().parse(source, context=context)
    assert document.parser.key == "generic.csv"
    assert document.rows[0].amount_cents == 125


@pytest.mark.parametrize("account", ["999999", None])
def test_rbc_rejects_wrong_or_unavailable_account(account):
    source = ImportSource("rbc.csv", (RBC_HEADER + "2026-01-20,000001,1,Deposit,\n").encode())
    with pytest.raises(ValueError, match="different account number"):
        RbcTransactionCsvParser().parse(source, context=ParseContext("RBC", account))


def test_rbc_checks_every_account_not_only_first_row():
    source = ImportSource(
        "rbc.csv",
        (RBC_HEADER + "2026-01-20,000001,1,Deposit,\n2026-01-21,999999,2,Deposit,\n").encode(),
    )
    with pytest.raises(ValueError, match="row 3"):
        RbcTransactionCsvParser().parse(source, context=ParseContext("RBC", "000001"))


@pytest.mark.parametrize(
    "parser,header",
    [(GenericCsvParser(), "Date,Amount\n"), (RbcTransactionCsvParser(), RBC_HEADER)],
)
def test_header_only_documents_do_not_invent_account_or_balance(parser, header):
    document = parser.parse(ImportSource("empty.csv", header.encode()), context=ParseContext())
    assert document is not None
    assert document.rows == ()
    assert document.account_number is None


@pytest.mark.parametrize("amount", ["NaN", "inf", "-inf", "1e1000", "bad", ""])
def test_non_finite_or_invalid_money_is_rejected(amount):
    with pytest.raises(ValueError):
        GenericCsvParser().parse(
            ImportSource("invalid.csv", f"Date,Amount\n2026-01-20,{amount}\n".encode()),
            context=ParseContext(),
        )


def test_source_balance_is_decimal_and_absence_is_not_zero():
    source = ImportSource(
        "exact.csv",
        b"Date,Amount,Balance\n2026-01-20,1000000000000000.01,1000000000000000.01\n"
        b"2026-01-21,0,0\n2026-01-22,0,\n",
    )
    document = GenericCsvParser().parse(source, context=ParseContext())
    assert document.rows[0].amount_cents == 100000000000000001
    assert document.rows[0].source_balance_cents == 100000000000000001
    assert document.rows[1].source_balance_cents == 0
    assert document.rows[2].source_balance_cents is None


@pytest.mark.parametrize("amount", ["1.005", "-1.005", "0.0049", "1000000000000000.01"])
def test_both_adapters_use_original_decimal_money(amount):
    generic = GenericCsvParser().parse(
        ImportSource("generic.csv", f"Date,Amount\n2026-01-20,{amount}\n".encode()),
        context=ParseContext(),
    )
    rbc = RbcTransactionCsvParser().parse(
        ImportSource("rbc.csv", (RBC_HEADER + f"2026-01-20,000001,{amount},Deposit,\n").encode()),
        context=ParseContext("RBC", "000001"),
    )
    assert rbc is not None
    assert generic.rows[0].amount_cents == rbc.rows[0].amount_cents == to_cents(Decimal(amount))


@pytest.mark.parametrize("balance", ["NaN", "Infinity", "invalid"])
def test_invalid_printed_balance_is_rejected(balance):
    with pytest.raises(ValueError):
        GenericCsvParser().parse(
            ImportSource("invalid.csv", f"Date,Amount,Balance\n2026-01-20,1,{balance}\n".encode()),
            context=ParseContext(),
        )


@pytest.mark.parametrize("value", ["20260120", "2026-W04-2"])
def test_adapter_canonicalizes_iso_dates_and_keeps_source_date(value):
    document = GenericCsvParser().parse(
        ImportSource("iso.csv", f"Date,Amount\n{value},1\n".encode()), context=ParseContext()
    )
    assert document.rows[0].transaction_date == "2026-01-20"
    assert value in document.rows[0].raw_data


def test_invalid_date_fails_without_returning_partial_document():
    with pytest.raises(ValueError):
        GenericCsvParser().parse(
            ImportSource("invalid.csv", b"Date,Amount\n2026-01-20,1\n2026-02-30,2\n"),
            context=ParseContext(),
        )


def test_recognized_but_malformed_rbc_layout_does_not_fall_back():
    with pytest.raises(ValueError, match="Unrecognized CSV format"):
        RbcTransactionCsvParser().parse(
            ImportSource("bad-rbc.csv", "Date de l'opération,CAD$\n2026-01-20,1\n".encode()),
            context=ParseContext(),
        )


def test_adapter_does_not_trust_legacy_amount_when_raw_evidence_is_missing():
    with pytest.raises(ValueError, match="row 2"):
        parsed_csv_rows(
            (CsvTransactionRow(2, "2026-01-20", 1.0, None, None, "{}"),), amount_columns=("amount",)
        )


@pytest.mark.parametrize(
    "parser,header,body",
    [
        (GenericCsvParser(), "Date,Amount", "2026-01-20,1,extra"),
        (GenericCsvParser(), "Date,Amount,Description", "2026-01-20,1"),
        (GenericCsvParser(), "Date,Amount,Memo", "2026-01-20,1"),
        (GenericCsvParser(), "Date,Amount,Payee", "2026-01-20,1"),
        (RbcTransactionCsvParser(), RBC_HEADER.strip(), "2026-01-20,000001,1,Deposit,,extra"),
        (RbcTransactionCsvParser(), RBC_HEADER.strip(), "2026-01-20,000001,1"),
    ],
)
def test_malformed_row_shape_raises_value_error(parser, header, body):
    with pytest.raises(ValueError):
        parser.parse(
            ImportSource("malformed.csv", f"{header}\n{body}\n".encode()),
            context=ParseContext("RBC", "000001"),
        )


@pytest.mark.parametrize("context_account", [None, "", "--", "letters"])
@pytest.mark.parametrize("source_account", ["", "--", "letters"])
def test_rbc_rejects_empty_normalized_account_evidence(context_account, source_account):
    with pytest.raises(ValueError):
        RbcTransactionCsvParser().parse(
            ImportSource(
                "rbc.csv", (RBC_HEADER + f"2026-01-20,{source_account},1,Deposit,\n").encode()
            ),
            context=ParseContext("RBC", context_account),
        )


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"Date,Amount,\n2026-01-20,1,ignored\n",
        b"Date,Amount, amount \n2026-01-20,1,2\n",
        b'Date,Amount\n"2026-01-20,1\n',
    ],
)
def test_generic_rejects_ambiguous_headers_and_malformed_quotes(content):
    with pytest.raises(ValueError):
        GenericCsvParser().parse(ImportSource("invalid.csv", content), context=ParseContext())


def test_rbc_fallback_does_not_validate_another_formats_row_shape():
    source = ImportSource("generic.csv", b"Date,Amount\n2026-01-20,1,extra\n")
    assert RbcTransactionCsvParser().parse(source, context=ParseContext()) is None
    with pytest.raises(ValueError):
        GenericCsvParser().parse(source, context=ParseContext())


def test_empty_and_literal_none_descriptions_remain_source_evidence():
    document = GenericCsvParser().parse(
        ImportSource(
            "descriptions.csv", b"Date,Amount,Description\n2026-01-20,1,\n2026-01-21,2,None\n"
        ),
        context=ParseContext(),
    )
    assert [r.description for r in document.rows] == ["", "None"]
    assert '"Description": ""' in document.rows[0].raw_data


def test_rbc_quoted_description_and_explicit_empty_secondary_description_are_valid():
    document = RbcTransactionCsvParser().parse(
        ImportSource(
            "quoted.csv", (RBC_HEADER + '2026-01-20,000001,1,"Credit, savings",\n').encode()
        ),
        context=ParseContext("RBC", "000001"),
    )
    assert document is not None
    assert document.rows[0].description == "Credit, savings"
