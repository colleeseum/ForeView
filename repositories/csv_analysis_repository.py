# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from domain.csv_analysis_snapshot import CsvAnalysisSnapshot
from domain.csv_ledger_row import CsvLedgerRow
from domain.validation_error import ValidationError
from repositories.account_repository import AccountRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.reconciliation_checkpoint_repository import ReconciliationCheckpointRepository


class CsvAnalysisRepository:
    """Capture a committed read snapshot using a dedicated read-only connection.

    No schema initialization, repair or caller-owned transaction is involved.
    Closing the connection releases the read transaction even on validation errors.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def read(self, account_id: int, file_hash: str) -> CsvAnalysisSnapshot:
        uri = self._database_path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.execute("BEGIN")
            account = AccountRepository(connection).get(account_id)
            if account is None:
                raise ValidationError("input_account_not_found", "Account not found")
            batch = ImportBatchRepository(connection).get_by_hash(file_hash)
            rows = connection.execute(
                """SELECT transaction_date, amount_cents, description, balance_after_cents
                   FROM transactions WHERE account_id = ? ORDER BY id""",
                (account_id,),
            ).fetchall()
            checkpoints = ReconciliationCheckpointRepository(connection).active_for_account(
                account_id
            )
            return CsvAnalysisSnapshot(
                account,
                batch,
                tuple(CsvLedgerRow(str(r[0]), int(r[1]), r[2], r[3]) for r in rows),
                tuple(checkpoints),
            )
