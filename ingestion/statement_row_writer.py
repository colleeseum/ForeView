# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Store parsed statement rows as raw evidence plus transactions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ingestion.reconciled_period_guard import ReconciledPeriodGuard
from ingestion.recorded_transaction_matcher import DEFAULT_IDENTITY, RecordedTransactionMatcher
from ingestion.row_counts import RowCounts
from repositories.raw_transaction_repository import RawTransactionRepository
from repositories.transaction_repository import TransactionRepository

StatementRow = Mapping[str, Any]


class StatementRowWriter:
    """Store parsed statement rows as raw evidence plus deduplicated transactions."""

    def __init__(self, connection: sqlite3.Connection, *, allow_reconciled: bool = False) -> None:
        self._connection = connection
        # Whether rows may enter reconciled periods; see ReconciledPeriodGuard.
        self._allow_reconciled = allow_reconciled
        self._raw_transactions = RawTransactionRepository(connection)
        self._transactions = TransactionRepository(connection)

    def write(
        self,
        batch_id: int,
        account_id: int,
        rows: Iterable[StatementRow],
        *,
        source: str,
        row_offset: int = 0,
        raw_fields: Mapping[str, Any] | None = None,
        transaction_fields: Mapping[str, Any] | None = None,
        identity: Sequence[str] = DEFAULT_IDENTITY,
    ) -> RowCounts:
        """Write rows and count them.

        ``raw_fields`` are stored with each raw row; ``transaction_fields``
        override the transaction values read from the row without being stored
        as raw evidence. Every row is kept as raw evidence, but a row matching a
        transaction the account already holds from another import, compared on
        the ``identity`` columns, is counted as a duplicate instead of stored again.
        """
        overrides = transaction_fields or {}
        recorded = RecordedTransactionMatcher(self._transactions, account_id, identity)
        guard = ReconciledPeriodGuard(self._connection, allow=self._allow_reconciled)
        imported = 0
        duplicates = 0
        for row_number, row in enumerate(rows, start=row_offset + 1):
            raw_data = json.dumps({"source": source, **(raw_fields or {}), **row}, sort_keys=True)
            # The row number is part of the hash so identical rows in one file are all kept.
            row_hash = hashlib.sha256(f"{row_number}:{raw_data}".encode()).hexdigest()
            raw = self._raw_transactions.add_if_new(batch_id, row_number, row_hash, raw_data)
            values = {**row, **overrides}
            transaction_type = values.get("transaction_type", "unclassified")
            if raw is None or recorded.is_recorded(
                {
                    "transaction_date": values["date"],
                    "amount": values["amount"],
                    "description": values.get("description"),
                    "transaction_type": transaction_type,
                    # Statement rows carry the balance the institution printed, if any.
                    "balance_after": values.get("balance"),
                }
            ):
                duplicates += 1
                continue
            transaction = self._transactions.create_if_absent(
                account_id,
                values["date"],
                values["amount"],
                raw_transaction_id=raw.id,
                description=values.get("description"),
                balance_after=values.get("balance"),
                category=values.get("category"),
                transaction_type=transaction_type,
            )
            if transaction is not None:
                imported += 1
                guard.admit(account_id, transaction.transaction_date)
        guard.finish()
        return RowCounts(imported, duplicates)
