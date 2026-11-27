# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Adapt existing CSV layout evidence without using its legacy float money values."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from decimal import Decimal, InvalidOperation

from domain.money import to_cents
from domain.validation_error import ValidationError
from ingestion.csv_format import CsvTransactionRow, csv_numeric_text
from ingestion.parsing.parsed_transaction import ParsedTransaction
from ingestion.raw_sources import CSV_BALANCE_COLUMNS


def source_field(raw_data: str, columns: Sequence[str]) -> str | None:
    """Use the same normalized-header precedence as the layout parser."""
    raw = json.loads(raw_data)
    fields = {key.strip().lower(): key for key in raw if key}
    for column in columns:
        if column in fields:
            return raw[fields[column]]
    return None


def parsed_csv_rows(
    rows: Iterable[CsvTransactionRow], *, amount_columns: Sequence[str]
) -> tuple[ParsedTransaction, ...]:
    parsed = []
    for row in rows:
        try:
            # Re-read original source text. Converting row.amount would retain
            # rounding already introduced by the legacy float representation.
            amount = to_cents(Decimal(csv_numeric_text(source_field(row.raw_data, amount_columns))))
            balance = (
                None
                if row.balance_after is None
                else to_cents(
                    Decimal(csv_numeric_text(source_field(row.raw_data, CSV_BALANCE_COLUMNS)))
                )
            )
        except (InvalidOperation, ValueError, ValidationError) as error:
            raise ValueError(f"Invalid monetary evidence on CSV row {row.row_number}") from error
        parsed.append(
            ParsedTransaction(
                row_number=row.row_number,
                transaction_date=row.transaction_date,
                amount_cents=amount,
                description=row.description,
                source_balance_cents=balance,
                raw_data=row.raw_data,
            )
        )
    return tuple(parsed)
