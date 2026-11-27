# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Validate source structure before legacy DictReader normalization loses cells."""

import csv
import io


def validate_csv_shape(content: bytes, *, recognition_column: str | None = None) -> None:
    """Reject ambiguous headers, ragged records and malformed quoting.

    An optional recognition column preserves a provider's None/fallback decision
    for other layouts. Empty cells are allowed; missing declared cells are not.
    """
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        fields = [field.strip().lower() for field in reader.fieldnames or ()]
        if recognition_column is not None and recognition_column not in fields:
            return
        if not fields:
            raise ValueError("CSV file has no header row")
        if any(not field for field in fields) or len(set(fields)) != len(fields):
            raise ValueError("CSV header names must be non-empty and unique")
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row {row_number} does not match the header columns")
    except csv.Error as error:
        raise ValueError("Malformed CSV quoting") from error
