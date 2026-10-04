# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Achieva document importers wired to their parsers and the PDF reader."""

from __future__ import annotations

import sqlite3

from ingestion.pdf_document import open_pdf
from institutions.achieva.parser import is_achieva_gic_pdf, parse_achieva_gic_pdf

from .import_service import AchievaImportService

__all__ = ["import_achieva_gic_pdf", "is_achieva_gic_pdf"]


def import_achieva_gic_pdf(
    connection: sqlite3.Connection,
    parent_account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | float | str | None]:
    return AchievaImportService(
        connection,
        parser=parse_achieva_gic_pdf,
        pdf_opener=open_pdf,
        allow_reconciled=allow_reconciled,
    ).import_gic(parent_account_id, filename, content)
