# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import csv
import io
import json

from ingestion.csv_format import CsvTransactionRow, csv_date, csv_number, digits

REQUIRED_FIELDS = {"date de l'opération", "numéro du compte", "cad$", "description 1"}


def parse_transactions(
    content: bytes, account_number: str | None, filename: str
) -> list[CsvTransactionRow] | None:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    fields = {field.strip().lower(): field for field in reader.fieldnames or () if field}
    if "date de l'opération" not in fields:
        return None
    if not REQUIRED_FIELDS.issubset(fields):
        raise ValueError(
            'Unrecognized CSV format for institution "RBC". See transaction import help.'
        )
    date_field = fields["date de l'opération"]
    account_field = fields["numéro du compte"]
    amount_field = fields["cad$"]
    description_field = fields["description 1"]
    description2_field = fields.get("description 2")
    normalized = []
    for row_number, row in enumerate(reader, start=2):
        try:
            amount = csv_number(row[amount_field])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid amount on CSV row {row_number}") from error
        if digits(row[account_field]) != digits(account_number):
            raise ValueError(f"{filename} contains a different account number on row {row_number}")
        description = str(row[description_field]).strip()
        if description2_field and row.get(description2_field):
            description = " ".join(
                part for part in (description, str(row[description2_field]).strip()) if part
            )
        normalized.append(
            CsvTransactionRow(
                row_number=row_number,
                transaction_date=csv_date(row[date_field]),
                amount=amount,
                description=description,
                balance_after=None,
                raw_data=json.dumps(row, sort_keys=True),
            )
        )
    return normalized
