# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from dataclasses import dataclass, field

from domain.account import Account
from domain.csv_ledger_row import CsvLedgerRow
from domain.import_batch import ImportBatch
from domain.reconciliation_checkpoint import ReconciliationCheckpoint


@dataclass(frozen=True, slots=True)
class CsvAnalysisSnapshot:
    """Single committed read view, closed before analysis returns to the caller."""

    account: Account = field(repr=False)
    existing_batch: ImportBatch | None = field(repr=False)
    ledger: tuple[CsvLedgerRow, ...] = field(repr=False)
    checkpoints: tuple[ReconciliationCheckpoint, ...] = field(repr=False)
