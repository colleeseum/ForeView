from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ingestion.raw_sources import CSV_BALANCE_COLUMNS


@dataclass(frozen=True, slots=True)
class CsvTransactionRow:
    """One normalized transaction row and its original CSV representation."""

    row_number: int
    transaction_date: str
    amount: float
    description: str | None
    balance_after: float | None
    raw_data: str


def parse_csv_transactions(
    content: bytes,
    *,
    institution: str | None,
    account_number: str | None,
    filename: str,
) -> list[CsvTransactionRow]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row")
    _profile(reader.fieldnames, institution)
    fields = {field.strip().lower(): field for field in reader.fieldnames if field}
    date_field: str | None
    amount_field: str | None
    description_field: str | None
    account_field: str | None
    description2_field: str | None
    balance_field: str | None
    account_field = None
    date_field = next(
        (fields[key] for key in ("date", "transaction date", "posted date") if key in fields),
        None,
    )
    amount_field = next(
        (fields[key] for key in ("amount", "transaction amount") if key in fields), None
    )
    description_field = next(
        (fields[key] for key in ("description", "memo", "payee") if key in fields), None
    )
    description2_field = None
    balance_field = next((fields[key] for key in CSV_BALANCE_COLUMNS if key in fields), None)
    if not date_field or not amount_field:
        raise ValueError("CSV must contain Date and Amount columns")
    required_date_field = date_field
    required_amount_field = amount_field

    normalized = []
    for row_number, row in enumerate(reader, start=2):
        try:
            amount = csv_number(row[required_amount_field])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid amount on CSV row {row_number}") from error
        if account_field and digits(row[account_field]) != digits(account_number):
            raise ValueError(f"{filename} contains a different account number on row {row_number}")
        balance = None
        if balance_field and row.get(balance_field):
            balance = csv_number(row[balance_field])
        description = str(row[description_field]).strip() if description_field else None
        if description2_field and row.get(description2_field):
            description = " ".join(
                part for part in (description, str(row[description2_field]).strip()) if part
            )
        normalized.append(
            CsvTransactionRow(
                row_number=row_number,
                transaction_date=csv_date(row[required_date_field]),
                amount=amount,
                description=description,
                balance_after=balance,
                raw_data=json.dumps(row, sort_keys=True),
            )
        )
    return normalized


def csv_number(value: object) -> float:
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if not text:
        raise ValueError("empty amount")
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    return float(text)


def csv_date(value: object) -> str:
    text = str(value or "").strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d%b%Y", "%d%b%y", "%d%B%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _profile(fieldnames: Sequence[str], institution: str | None) -> str:
    fields = {field.strip().lower() for field in fieldnames if field}
    if any(key in fields for key in ("date", "transaction date", "posted date")) and any(
        key in fields for key in ("amount", "transaction amount")
    ):
        return "generic"
    label = institution.strip() if institution else "unknown"
    raise ValueError(
        f'Unrecognized CSV format for institution "{label}". See transaction import help.'
    )
