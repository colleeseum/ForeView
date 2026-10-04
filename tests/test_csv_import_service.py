# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from ingestion.csv_format import csv_date, csv_number, parse_csv_transactions
from repositories.import_batch_repository import ImportBatchRepository
from repositories.raw_transaction_repository import RawTransactionRepository
from services.csv_import_service import CsvImportService
from tests.support import create_account, ensure_domain_schema, import_csv_transactions


class CsvImportServiceTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(
        connection: sqlite3.Connection,
        *,
        institution: str = "Generic CSV",
        number: str = "SYN-001",
    ) -> int:
        return create_account(
            connection,
            "CSV account",
            "non_registered",
            account_number=number,
            institution=institution,
        )

    @staticmethod
    def _stored_rows(connection: sqlite3.Connection):
        return [
            tuple(row)
            for row in connection.execute(
                """SELECT t.transaction_date, t.amount, t.description, t.balance_after,
                          r.row_number, r.raw_data
                   FROM transactions t JOIN raw_transactions r ON r.id = t.raw_transaction_id
                   ORDER BY t.id"""
            ).fetchall()
        ]

    def test_service_matches_existing_generic_csv_import_contract(self):
        content = (
            b"Date,Amount,Description,Balance\n"
            b"31Oct2025,$25.56,Interest,$471535.36\n"
            b"2025-11-01,(10.00),Purchase,471525.36\n"
        )
        with self._connection() as legacy, self._connection() as extracted:
            legacy_account = self._account(legacy)
            extracted_account = self._account(extracted)

            expected = import_csv_transactions(legacy, legacy_account, "history.csv", content)
            actual = CsvImportService(extracted).import_transactions(
                extracted_account, "history.csv", content
            )

            self.assertEqual(actual, expected)
            self.assertEqual(self._stored_rows(extracted), self._stored_rows(legacy))

    def test_service_matches_existing_rbc_profile_and_duplicate_contract(self):
        content = (
            "Type de compte,Numéro du compte,Date de l'opération,Description 1,"
            "Description 2,CAD$\n"
            "Chèques,99999-7777777,1/2/2025,DÉPÔT,CHÈQUE,21.98\n"
        ).encode()
        with self._connection() as legacy, self._connection() as extracted:
            legacy_account = self._account(legacy, institution="RBC", number="99999-7777777")
            extracted_account = self._account(extracted, institution="RBC", number="99999-7777777")

            expected = import_csv_transactions(legacy, legacy_account, "rbc.csv", content)
            actual = CsvImportService(extracted).import_transactions(
                extracted_account, "rbc.csv", content
            )
            duplicate = CsvImportService(extracted).import_transactions(
                extracted_account, "copy.csv", content
            )

            self.assertEqual(actual, expected)
            self.assertEqual(self._stored_rows(extracted), self._stored_rows(legacy))
            self.assertEqual(duplicate["status"], "already_imported")
            self.assertEqual(duplicate["duplicates"], 1)

    def test_rbc_csv_is_recognized_without_institution_metadata(self):
        content = (
            "Type de compte,Numéro du compte,Date de l'opération,Description 1,"
            "Description 2,CAD$\n"
            "Chèques,99999-7777777,2025-02-01,DÉPÔT,CHÈQUE,21.98\n"
        ).encode()
        with self._connection() as connection:
            account = self._account(connection, institution="", number="99999-7777777")

            result = CsvImportService(connection).import_transactions(account, "rbc.csv", content)

            self.assertEqual(result["imported"], 1)
            [row] = self._stored_rows(connection)
            self.assertEqual(row[:4], ("2025-02-01", 21.98, "DÉPÔT CHÈQUE", None))

    def test_parser_validation_has_no_persistence_side_effects(self):
        with self._connection() as connection:
            account = self._account(connection, institution="RBC", number="123-456")
            cases = (
                (b"", "no header"),
                (b"Wrong,Columns\n1,2\n", "Unrecognized CSV"),
                (b"Date,Amount\n2026-01-01,invalid\n", "Invalid amount"),
                (
                    "Numéro du compte,Date de l'opération,Description 1,CAD$\n"
                    "999,1/1/2026,Deposit,1\n".encode(),
                    "different account number",
                ),
            )
            for content, message in cases:
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    CsvImportService(connection).import_transactions(
                        account, "invalid.csv", content
                    )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0], 0
            )

    def test_csv_value_normalization_contract(self):
        self.assertEqual(csv_number("$1,234.56"), 1234.56)
        self.assertEqual(csv_number("(12.50)"), -12.5)
        self.assertEqual(csv_date("31Oct2025"), "2025-10-31")
        self.assertEqual(csv_date("unknown"), "unknown")
        rows = parse_csv_transactions(
            b"Posted Date,Transaction Amount,Memo\n2026-01-01,10,Deposit\n",
            institution=None,
            account_number=None,
            filename="generic.csv",
        )
        self.assertEqual(rows[0].description, "Deposit")

    def test_legacy_date_repair_is_idempotent(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = CsvImportService(connection)
            connection.execute(
                """INSERT INTO transactions(
                       account_id, transaction_date, amount, transaction_type
                   ) VALUES (?, '31Oct2025', 10, 'unclassified')""",
                (account,),
            )

            self.assertEqual(repository.repair_legacy_dates(), 1)
            self.assertEqual(repository.repair_legacy_dates(), 0)
            self.assertEqual(
                connection.execute("SELECT transaction_date FROM transactions").fetchone()[0],
                "2025-10-31",
            )


class RawTransactionRepositoryTests(unittest.TestCase):
    def test_raw_rows_are_immutable_and_deduplicated_within_batch(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        ensure_domain_schema(connection)
        account = create_account(connection, "Account", "non_registered", account_number="RAW-001")
        batch = ImportBatchRepository(connection).create(account, "source.csv", "source-hash")
        repository = RawTransactionRepository(connection)
        raw_data = '{"Amount": "10"}'
        row_hash = hashlib.sha256(raw_data.encode()).hexdigest()

        row = repository.add_if_new(batch.id, 2, row_hash, raw_data)

        self.assertIsNotNone(row)
        self.assertEqual(repository.get(row.id), row)
        self.assertEqual(repository.list_for_batch(batch.id), [row])
        self.assertIsNone(repository.add_if_new(batch.id, 3, row_hash, raw_data))
        self.assertIsNone(repository.get(None))
        self.assertIsNone(repository.get(999))
        with self.assertRaises(FrozenInstanceError):
            row.raw_data = "changed"  # type: ignore[misc]
