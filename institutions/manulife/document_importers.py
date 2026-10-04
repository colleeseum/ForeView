# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Manulife document importers wired to their parsers and the PDF reader."""

from __future__ import annotations

import sqlite3

from ingestion.pdf_document import open_pdf, pdf_page_texts
from institutions.manulife.parser import is_manulife_rrsp_pdf, parse_rrsp_statement

from .import_service import ManulifeImportService

__all__ = ["import_manulife_rrsp_pdf", "is_manulife_rrsp_pdf"]


def import_manulife_rrsp_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | float | str]:
    return ManulifeImportService(
        connection,
        parser=parse_rrsp_statement,
        pdf_opener=open_pdf,
        allow_reconciled=allow_reconciled,
    ).import_rrsp(account_id, filename, content)


def rrsp_account_number(content: bytes, filename: str) -> str:
    return str(parse_rrsp_statement(pdf_page_texts(open_pdf, content), filename)["account_number"])
