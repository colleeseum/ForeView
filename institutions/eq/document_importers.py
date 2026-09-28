"""EQ Bank document importers wired to their parsers and the PDF reader."""

from __future__ import annotations

import sqlite3

from ingestion.pdf_document import open_pdf
from institutions.eq.parser import parse_eq_pdf_transactions

from .import_service import EqImportService

__all__ = ["import_eq_statement_pdf"]


def import_eq_statement_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | str]:
    return EqImportService(
        connection,
        parser=parse_eq_pdf_transactions,
        pdf_opener=open_pdf,
        allow_reconciled=allow_reconciled,
    ).import_statement(account_id, filename, content)
