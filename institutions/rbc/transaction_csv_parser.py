# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from ingestion.csv_format import digits
from ingestion.parsing.csv_evidence import parsed_csv_rows, source_field
from ingestion.parsing.csv_shape import validate_csv_shape
from ingestion.parsing.import_source import ImportSource
from ingestion.parsing.parse_context import ParseContext
from ingestion.parsing.parsed_transaction_document import ParsedTransactionDocument
from ingestion.parsing.parser_identity import ParserIdentity
from institutions.rbc.csv_parser import parse_transactions


class RbcTransactionCsvParser:
    """RBC layout adapter; None delegates unrecognized formats to generic CSV."""

    identity = ParserIdentity("rbc.transactions.csv", "2026.11.26.1")

    def parse(
        self, source: ImportSource, *, context: ParseContext
    ) -> ParsedTransactionDocument | None:
        validate_csv_shape(source.content, recognition_column="date de l'opération")
        rows = parse_transactions(source.content, context.account_number, source.filename)
        if rows is None:
            return None
        for row in rows:
            if not digits(context.account_number) or not digits(
                source_field(row.raw_data, ("numéro du compte",))
            ):
                raise ValueError(f"Missing account number evidence on CSV row {row.row_number}")
        return ParsedTransactionDocument(
            source=source,
            parser=self.identity,
            rows=parsed_csv_rows(rows, amount_columns=("cad$",)),
            account_number=source_field(rows[0].raw_data, ("numéro du compte",)) if rows else None,
        )
