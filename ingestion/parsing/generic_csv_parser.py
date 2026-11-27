# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from ingestion.csv_format import CSV_AMOUNT_COLUMNS, parse_csv_transactions
from ingestion.parsing.csv_evidence import parsed_csv_rows
from ingestion.parsing.csv_shape import validate_csv_shape
from ingestion.parsing.import_source import ImportSource
from ingestion.parsing.parse_context import ParseContext
from ingestion.parsing.parsed_transaction_document import ParsedTransactionDocument
from ingestion.parsing.parser_identity import ParserIdentity


class GenericCsvParser:
    """Pure terminal Date/Amount fallback using the existing layout policy."""

    identity = ParserIdentity("generic.csv", "2026.11.26.1")

    def parse(self, source: ImportSource, *, context: ParseContext) -> ParsedTransactionDocument:
        validate_csv_shape(source.content)
        rows = parse_csv_transactions(
            source.content,
            institution=context.institution,
            account_number=context.account_number,
            filename=source.filename,
        )
        return ParsedTransactionDocument(
            source, self.identity, parsed_csv_rows(rows, amount_columns=CSV_AMOUNT_COLUMNS)
        )
