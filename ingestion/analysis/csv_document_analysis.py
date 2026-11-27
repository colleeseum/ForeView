# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from dataclasses import dataclass, field

from domain.account import Account
from domain.import_batch import ImportBatch
from ingestion.analysis.csv_row_analysis import CsvRowAnalysis
from ingestion.parsing.parsed_transaction_document import ParsedTransactionDocument


@dataclass(frozen=True, slots=True)
class CsvDocumentAnalysis:
    """Read-only transaction decisions, not a complete effect proposal or write approval.

    An exact-file match retains its original batch/account provenance. Its rows
    are not rematched: legacy duplicate counts come from that batch's row_count.
    """

    document: ParsedTransactionDocument = field(repr=False)
    account: Account = field(repr=False)
    existing_batch: ImportBatch | None = field(repr=False)
    rows: tuple[CsvRowAnalysis, ...] = field(repr=False)
    locked_through: str | None

    @property
    def status(self) -> str:
        return "already_imported" if self.existing_batch is not None else "analysed"

    @property
    def new_count(self) -> int:
        return sum(not row.duplicate for row in self.rows)

    @property
    def duplicate_count(self) -> int:
        if self.existing_batch is not None:
            return self.existing_batch.row_count
        return sum(row.duplicate for row in self.rows)

    @property
    def reconciled_period_count(self) -> int:
        return sum(row.enters_reconciled_period for row in self.rows)
