# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from dataclasses import dataclass, field

from ingestion.parsing.parsed_transaction import ParsedTransaction


@dataclass(frozen=True, slots=True)
class CsvRowAnalysis:
    """One source occurrence's matching and locked-period decision."""

    row: ParsedTransaction = field(repr=False)
    duplicate: bool
    enters_reconciled_period: bool
