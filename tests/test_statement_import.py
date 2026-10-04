# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import json
import sqlite3
import unittest

from ingestion.pdf_document import pdf_page_texts
from ingestion.raw_sources import has_bank_reported_balance
from ingestion.row_counts import RowCounts
from ingestion.statement_import import account_digits, already_imported, unrecognized_pdf
from ingestion.statement_row_writer import StatementRowWriter
from institution_support.registry import institution_registry
from institutions.eq.raw_sources import EQ_PDF
from institutions.rbc.raw_sources import RBC_TFSA_PDF
from repositories.account_repository import AccountRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.raw_transaction_repository import RawTransactionRepository
from repositories.transaction_repository import TransactionRepository
from services.database_initialization import ensure_domain_schema


def _row(date: str, amount: float, **values):
    return {"date": date, "amount": amount, "description": f"Row {date}", **values}


class StatementRowWriterTests(unittest.TestCase):
    def setUp(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        ensure_domain_schema(connection)
        self.connection = connection
        self.account = (
            AccountRepository(connection)
            .create("Savings", "non_registered", account_number="SAV-1", institution="Test")
            .id
        )
        self.batch = ImportBatchRepository(connection).create(self.account, "a.pdf", "hash").id
        self.writer = StatementRowWriter(connection)

    def _transactions(self):
        return TransactionRepository(self.connection).list_for_account(self.account)

    def _raw(self):
        return [
            json.loads(raw.raw_data)
            for raw in RawTransactionRepository(self.connection).list_for_batch(self.batch)
        ]

    def test_rows_become_raw_evidence_and_transactions(self):
        counts = self.writer.write(
            self.batch,
            self.account,
            [_row("2026-01-01", 10.0, balance=110.0, category="Interest")],
            source=EQ_PDF,
        )

        self.assertEqual(counts, RowCounts(imported=1, duplicates=0))
        [transaction] = self._transactions()
        self.assertEqual(transaction.balance_after, 110.0)
        self.assertEqual(transaction.category, "Interest")
        self.assertEqual(transaction.transaction_type, "unclassified")
        self.assertEqual(self._raw()[0]["source"], "eq_pdf")

    def _second_batch(self):
        return ImportBatchRepository(self.connection).create(self.account, "b.pdf", "hash-2").id

    def _raw_in(self, batch_id):
        return RawTransactionRepository(self.connection).list_for_batch(batch_id)

    def test_identical_rows_in_one_file_are_all_kept_and_not_imported_twice(self):
        rows = [_row("2026-01-01", 10.0), _row("2026-01-01", 10.0)]

        counts = self.writer.write(self.batch, self.account, rows, source=EQ_PDF)
        again = self.writer.write(self._second_batch(), self.account, rows, source=EQ_PDF)

        self.assertEqual(counts, RowCounts(imported=2, duplicates=0))
        self.assertEqual(again, RowCounts(imported=0, duplicates=2))
        self.assertEqual(len(self._transactions()), 2)

    def test_rows_recorded_by_another_import_keep_raw_evidence_only(self):
        self.writer.write(self.batch, self.account, [_row("2026-01-01", 10.0)], source=EQ_PDF)
        second = self._second_batch()

        counts = self.writer.write(
            second,
            self.account,
            [_row("2026-01-01", 10.0), _row("2026-01-02", 20.0)],
            source=EQ_PDF,
        )

        self.assertEqual(counts, RowCounts(imported=1, duplicates=1))
        self.assertEqual([t.amount for t in self._transactions()], [10.0, 20.0])
        self.assertEqual(len(self._raw_in(second)), 2)

    def test_raw_fields_are_stored_and_transaction_fields_are_not(self):
        self.writer.write(
            self.batch,
            self.account,
            [_row("2026-01-01", 5.0, balance=99.0)],
            source=RBC_TFSA_PDF,
            row_offset=3,
            raw_fields={"account_id": self.account},
            transaction_fields={"balance": None, "transaction_type": "interest"},
        )

        [raw] = RawTransactionRepository(self.connection).list_for_batch(self.batch)
        self.assertEqual(raw.row_number, 4)
        stored = json.loads(raw.raw_data)
        self.assertEqual(stored["account_id"], self.account)
        self.assertEqual(stored["balance"], 99.0)
        self.assertNotIn("transaction_type", stored)
        [transaction] = self._transactions()
        self.assertIsNone(transaction.balance_after)
        self.assertEqual(transaction.transaction_type, "interest")

    def test_row_counts_add(self):
        self.assertEqual(RowCounts(1, 2) + RowCounts(3, 4), RowCounts(4, 6))


class StatementImportHelperTests(unittest.TestCase):
    def test_account_digits_ignore_formatting_and_missing_values(self):
        self.assertEqual(account_digits("12-345 6"), "123456")
        self.assertEqual(account_digits(None), "")

    def test_already_imported_reports_the_original_batch(self):
        from domain.import_batch import ImportBatch

        batch = ImportBatch(7, 1, "a.pdf", "hash", "2026-01-01", 3)
        self.assertEqual(
            already_imported(batch),
            {"batch_id": 7, "imported": 0, "duplicates": 3, "status": "already_imported"},
        )

    def test_pdf_page_texts_treat_empty_pages_as_blank(self):
        class Page:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class Pdf:
            pages = [Page("first"), Page(None)]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        self.assertEqual(pdf_page_texts(lambda _source: Pdf(), b"%PDF"), ["first", ""])

    def test_unrecognized_pdf_names_the_institution(self):
        self.assertIn('institution "RBC"', str(unrecognized_pdf("RBC")))


class BankReportedBalanceTests(unittest.TestCase):
    def test_sources_and_csv_columns(self):
        cases = [
            ("missing raw data", None, False),
            ("invalid json", "{not json", False),
            ("statement row with balance", {"source": "eq_pdf", "balance": 5.0}, True),
            ("statement row without balance", {"source": "rbc_tfsa_pdf", "balance": None}, False),
            ("statement balance of zero", {"source": "rbc_gic_pdf_cash", "balance": 0}, True),
            ("csv balance column", {"Date": "2026-01-01", " Balance ": "10"}, True),
            ("csv running balance column", {"Running Balance": "10"}, True),
            ("csv blank balance column", {"Balance": ""}, False),
            ("csv without balance column", {"Date": "2026-01-01", "Amount": "5"}, False),
            ("unknown source falls back to csv columns", {"source": "other", "balance": 5.0}, True),
        ]
        sources = institution_registry().statement_sources()
        for name, raw, expected in cases:
            with self.subTest(name):
                raw_data = raw if raw is None or isinstance(raw, str) else json.dumps(raw)
                self.assertIs(has_bank_reported_balance(raw_data, sources), expected)


if __name__ == "__main__":
    unittest.main()
