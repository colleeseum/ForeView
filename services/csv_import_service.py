# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
import re
import sqlite3

from ingestion.csv_format import csv_date, parse_csv_transactions
from ingestion.reconciled_period_guard import ReconciledPeriodGuard
from ingestion.recorded_transaction_matcher import RecordedTransactionMatcher
from ingestion.statement_import import already_imported, content_hash
from institution_support.registry import institution_registry
from repositories.account_repository import AccountRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.raw_transaction_repository import RawTransactionRepository
from repositories.transaction_repository import TransactionRepository


class CsvImportService:
    """Coordinate generic and institution-profiled CSV transaction imports."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._accounts = AccountRepository(connection)
        self._batches = ImportBatchRepository(connection)
        self._raw_transactions = RawTransactionRepository(connection)
        self._transactions = TransactionRepository(connection)

    def import_transactions(
        self, account_id: int, filename: str, content: bytes, *, allow_reconciled: bool = False
    ) -> dict[str, int | str]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        if existing:
            return already_imported(existing)
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError("Account not found")
        rows = None
        for parser in institution_registry().csv_parsers(account.institution):
            rows = parser(content, account.account_number, filename)
            if rows is not None:
                break
        if rows is None:
            rows = parse_csv_transactions(
                content,
                institution=account.institution,
                account_number=account.account_number,
                filename=filename,
            )
        with self._connection:
            batch_id = self._batches.create(account_id, filename, file_hash).id
            recorded = RecordedTransactionMatcher(self._transactions, account_id)
            guard = ReconciledPeriodGuard(self._connection, allow=allow_reconciled)
            imported = 0
            duplicates = 0
            for row in rows:
                # The row number is part of the hash so identical rows in one file are all kept.
                row_hash = hashlib.sha256(f"{row.row_number}:{row.raw_data}".encode()).hexdigest()
                raw = self._raw_transactions.add_if_new(
                    batch_id, row.row_number, row_hash, row.raw_data
                )
                if raw is None or recorded.is_recorded(
                    {
                        "transaction_date": row.transaction_date,
                        "amount": row.amount,
                        "description": row.description,
                        # Only set when the export has a Balance column.
                        "balance_after": row.balance_after,
                    }
                ):
                    duplicates += 1
                    continue
                transaction = self._transactions.create_if_absent(
                    account_id,
                    row.transaction_date,
                    row.amount,
                    raw_transaction_id=raw.id,
                    description=row.description,
                    balance_after=row.balance_after,
                )
                if transaction is not None:
                    imported += 1
                    guard.admit(account_id, transaction.transaction_date)
            guard.finish()
            self._batches.update_row_count(batch_id, imported)
        return {
            "batch_id": batch_id,
            "imported": imported,
            "duplicates": duplicates,
            "status": "imported",
        }

    def repair_legacy_dates(self) -> int:
        """Normalize dates from CSV imports created before all formats were supported."""
        repaired = 0
        for transaction_id, transaction_date in self._transactions.non_iso_dates():
            normalized = csv_date(transaction_date)
            if normalized != transaction_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
                self._transactions.update_date(transaction_id, normalized)
                repaired += 1
        if repaired:
            self._connection.commit()
        return repaired
