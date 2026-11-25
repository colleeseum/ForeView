# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass, field

from ingestion.parsing.import_source import ImportSource
from ingestion.parsing.parsed_transaction import ParsedTransaction
from ingestion.parsing.parser_identity import ParserIdentity


@dataclass(frozen=True, slots=True)
class ParsedTransactionDocument:
    """Ordered transaction evidence, not an analysed or approved write proposal.

    Repeated rows remain separate occurrences. Empty rows mean no transactions,
    not a zero balance. Provider-specific non-transaction evidence needs additional
    typed contracts before any such provider can participate in confirmation.
    """

    source: ImportSource = field(repr=False)
    parser: ParserIdentity
    rows: tuple[ParsedTransaction, ...] = field(repr=False)
    account_number: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source, ImportSource) or not isinstance(self.parser, ParserIdentity):
            raise TypeError("Parsed document requires source and parser identity values")
        rows = tuple(self.rows)
        if any(not isinstance(row, ParsedTransaction) for row in rows):
            raise TypeError("Parsed document rows must be parsed transactions")
        object.__setattr__(self, "rows", rows)
        if self.account_number is not None and not isinstance(self.account_number, str):
            raise TypeError("Parsed account number must be text or None")
