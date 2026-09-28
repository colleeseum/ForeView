"""Sun Life document importers wired to their parsers and the PDF reader."""

from __future__ import annotations

import sqlite3

from ingestion.pdf_document import open_pdf, pdf_page_texts
from institutions.sunlife.parser import (
    is_rrsp_statement_pdf as is_sunlife_rrsp_pdf,
)
from institutions.sunlife.parser import (
    is_transaction_history_pdf as is_sunlife_transaction_history_pdf,
)
from institutions.sunlife.parser import (
    parse_rrsp_statement as parse_sunlife_rrsp_statement,
)
from institutions.sunlife.parser import (
    parse_transaction_history as parse_sunlife_transaction_history,
)

from .import_service import SunLifeImportService

__all__ = [
    "import_sunlife_rrsp_pdf",
    "import_sunlife_transaction_history_pdf",
    "is_sunlife_rrsp_pdf",
    "is_sunlife_transaction_history_pdf",
]


def _service(
    connection: sqlite3.Connection, *, allow_reconciled: bool = False
) -> SunLifeImportService:
    return SunLifeImportService(
        connection,
        allow_reconciled=allow_reconciled,
        statement_parser=parse_sunlife_rrsp_statement,
        history_parser=parse_sunlife_transaction_history,
        pdf_opener=open_pdf,
    )


def import_sunlife_transaction_history_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | str | float]:
    return _service(connection, allow_reconciled=allow_reconciled).import_transaction_history(
        account_id, filename, content
    )


def import_sunlife_rrsp_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | float | str]:
    return _service(connection, allow_reconciled=allow_reconciled).import_rrsp_statement(
        account_id, filename, content
    )


def transaction_history_account_number(content: bytes, filename: str) -> str:
    return str(
        parse_sunlife_transaction_history(pdf_page_texts(open_pdf, content), filename)[
            "account_number"
        ]
    )


def rrsp_account_number(content: bytes, filename: str) -> str:
    return str(
        parse_sunlife_rrsp_statement(pdf_page_texts(open_pdf, content), filename)["account_number"]
    )
