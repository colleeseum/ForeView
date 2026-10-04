# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Exact payroll parameters from CRA's machine-readable T4127 tables."""

from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation

from .errors import RuleSourceFormatError


def payroll_record(
    content: bytes, table_label: str, row_label: str, source_name: str
) -> dict[str, Decimal]:
    """Return a labelled record keyed by the source's column headings."""
    text = content.decode("utf-8-sig", errors="replace")
    try:
        rows = [row for row in csv.reader(io.StringIO(text, newline="")) if row]
    except csv.Error as error:
        raise RuleSourceFormatError(f"Invalid CSV structure in {source_name}") from error
    headers = [row for row in rows if row[0].strip() == table_label]
    matches = [row for row in rows if row[0].strip() == row_label]
    if len(headers) != 1 or len(matches) != 1:
        raise RuleSourceFormatError(
            f"Expected one {table_label} header and one {row_label} row in {source_name}"
        )
    header, values = headers[0], matches[0]
    if len(header) != len(values):
        raise RuleSourceFormatError(f"Column count mismatch in {source_name}: {row_label}")
    try:
        return {
            name.strip(): Decimal(value.replace(",", "").strip())
            for name, value in zip(header[1:], values[1:], strict=True)
        }
    except InvalidOperation as error:
        raise RuleSourceFormatError(
            f"Invalid numeric value in {source_name}: {row_label}"
        ) from error
