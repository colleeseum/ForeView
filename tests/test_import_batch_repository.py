# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.import_batch_repository import ImportBatchRepository
from tests.support import create_account, ensure_domain_schema


class ImportBatchRepositoryTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(connection: sqlite3.Connection) -> int:
        return create_account(connection, "Import account", "cash", account_number="IMPORT-001")

    def test_create_and_retrieve_immutable_batch(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = ImportBatchRepository(connection)

            batch = repository.create(account, "statement.pdf", "hash-1", 12)

            self.assertEqual(batch.account_id, account)
            self.assertEqual(batch.filename, "statement.pdf")
            self.assertEqual(batch.file_hash, "hash-1")
            self.assertEqual(batch.row_count, 12)
            self.assertTrue(batch.imported_at)
            self.assertEqual(repository.get(batch.id), batch)
            self.assertEqual(repository.get_by_hash("hash-1"), batch)
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            self.assertIsNone(repository.get_by_hash("missing"))
            with self.assertRaises(FrozenInstanceError):
                batch.row_count = 0  # type: ignore[misc]

    def test_create_preserves_sqlite_unique_hash_behavior(self):
        with self._connection() as connection:
            repository = ImportBatchRepository(connection)
            repository.create(None, "first.csv", "same-hash")

            with self.assertRaises(sqlite3.IntegrityError) as error:
                repository.create(None, "second.csv", "same-hash")

            self.assertIn("import_batches.file_hash", str(error.exception))

    def test_get_or_create_preserves_existing_batch(self):
        with self._connection() as connection:
            first_account = self._account(connection)
            second_account = create_account(
                connection, "Other", "cash", account_number="IMPORT-002"
            )
            repository = ImportBatchRepository(connection)
            original = repository.get_or_create(
                first_account, "original", "stream-hash", row_count=3
            )

            repeated = repository.get_or_create(
                second_account, "replacement", "stream-hash", row_count=99
            )

            self.assertEqual(repeated, original)
            self.assertEqual(repeated.account_id, first_account)
            self.assertEqual(repeated.filename, "original")
            self.assertEqual(repeated.row_count, 3)

    def test_row_count_updates_match_batch_progress(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = ImportBatchRepository(connection)
            batch = repository.create(account, "transactions.csv", "hash-2")

            repository.update_row_count(batch.id, 7)

            self.assertEqual(repository.get(batch.id).row_count, 7)  # type: ignore[union-attr]

    def test_row_count_can_be_derived_from_linked_transactions(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = ImportBatchRepository(connection)
            batch = repository.create(account, "activities", "stream")
            other_batch = repository.create(account, "other", "other-stream")
            for row_number, target_batch in enumerate(
                (batch.id, batch.id, other_batch.id), start=1
            ):
                raw = connection.execute(
                    """INSERT INTO raw_transactions(batch_id, row_number, row_hash, raw_data)
                       VALUES (?, ?, ?, '{}')""",
                    (target_batch, row_number, f"raw-{row_number}"),
                )
                connection.execute(
                    """INSERT INTO transactions(
                           account_id, raw_transaction_id, transaction_date, amount, description
                       ) VALUES (?, ?, '2026-01-01', 1, ?)""",
                    (account, raw.lastrowid, f"Transaction {row_number}"),
                )

            repository.update_row_count_from_transactions(batch.id)

            self.assertEqual(repository.get(batch.id).row_count, 2)  # type: ignore[union-attr]
            self.assertEqual(repository.get(other_batch.id).row_count, 0)  # type: ignore[union-attr]

    def test_history_filters_by_account_and_type_and_applies_limit(self):
        with self._connection() as connection:
            repository = ImportBatchRepository(connection)
            cash = self._account(connection)
            tfsa = create_account(connection, "Savings", "tfsa", account_number="TFSA-001")
            first = repository.create(cash, "first.csv", "hash-1", 3)
            second = repository.create(cash, "second.csv", "hash-2", 1)
            other = repository.create(tfsa, "tfsa.pdf", "hash-3", 2)

            def ids(**filters):
                return [row["id"] for row in repository.history(**filters)]

            self.assertEqual(ids(), [other.id, second.id, first.id])
            self.assertEqual(ids(account_id=cash), [second.id, first.id])
            self.assertEqual(ids(account_type="tfsa"), [other.id])
            self.assertEqual(ids(account_id=cash, account_type="tfsa"), [])
            self.assertEqual(ids(limit=1), [other.id])
            [row] = repository.history(account_id=tfsa)
            self.assertEqual((row["account_number"], row["row_count"]), ("TFSA-001", 2))
            self.assertIsNone(row["reconciliation_status"])
