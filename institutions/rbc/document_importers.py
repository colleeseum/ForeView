# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""RBC document importers wired to their parsers and the PDF reader."""

from __future__ import annotations

import sqlite3

from ingestion.pdf_document import open_pdf, pdf_page_texts
from institutions.rbc.parser import (
    is_gic_transaction_history_pdf as is_rbc_gic_transaction_history_pdf,
)
from institutions.rbc.parser import (
    is_resp_gic_transaction_history_pdf as is_rbc_resp_gic_transaction_history_pdf,
)
from institutions.rbc.parser import (
    is_tfsa_gic_transaction_history_pdf as is_rbc_tfsa_gic_transaction_history_pdf,
)
from institutions.rbc.parser import (
    parse_deposit_statement_text,
)
from institutions.rbc.parser import (
    parse_gic_transaction_history as parse_rbc_gic_transaction_history,
)
from institutions.rbc.parser import (
    parse_tfsa_statement as parse_rbc_tfsa_statement,
)

from .deposit_import_service import RbcDepositImportService
from .document_inspector import RbcDocumentInspector
from .gic_history_import_service import RbcGicHistoryImportService
from .tfsa_import_service import RbcTfsaImportService

__all__ = [
    "import_rbc_gic_transaction_history_pdf",
    "import_rbc_resp_gic_transaction_history_pdf",
    "import_rbc_statement_pdf",
    "import_rbc_tfsa_pdf",
    "is_rbc_gic_transaction_history_pdf",
    "is_rbc_resp_gic_transaction_history_pdf",
    "is_rbc_tfsa_gic_transaction_history_pdf",
    "is_rbc_statement_pdf",
    "is_rbc_tfsa_pdf",
    "parse_rbc_statement_summary",
    "upsert_imported_gic",
]


def _inspector() -> RbcDocumentInspector:
    return RbcDocumentInspector(pdf_opener=open_pdf, deposit_parser=parse_deposit_statement_text)


def parse_rbc_statement_summary(
    content: bytes, filename: str = "statement.pdf"
) -> dict[str, object]:
    """Extract the stable summary fields from an RBC monthly statement PDF."""
    return _inspector().parse_deposit_summary(content, filename)


def is_rbc_statement_pdf(content: bytes) -> bool:
    return _inspector().is_deposit_statement(content)


def is_rbc_tfsa_pdf(content: bytes) -> bool:
    return _inspector().is_tfsa_document(content)


def import_rbc_gic_transaction_history_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | float | str]:
    return RbcGicHistoryImportService(
        connection,
        parser=parse_rbc_gic_transaction_history,
        pdf_opener=open_pdf,
        allow_reconciled=allow_reconciled,
    ).import_history(account_id, filename, content)


def import_rbc_resp_gic_transaction_history_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | float | str]:
    return import_rbc_gic_transaction_history_pdf(
        connection,
        account_id,
        filename,
        content,
        allow_reconciled=allow_reconciled,
    )


def _tfsa_service(
    connection: sqlite3.Connection, *, allow_reconciled: bool = False
) -> RbcTfsaImportService:
    return RbcTfsaImportService(
        connection,
        parser=parse_rbc_tfsa_statement,
        pdf_opener=open_pdf,
        allow_reconciled=allow_reconciled,
    )


def upsert_imported_gic(
    connection: sqlite3.Connection, account_id: int, gic: dict[str, object], filename: str
) -> int:
    return _tfsa_service(connection).upsert_gic(account_id, gic, filename)


def import_rbc_tfsa_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | float | str | None]:
    return _tfsa_service(connection, allow_reconciled=allow_reconciled).import_document(
        account_id, filename, content
    )


def import_rbc_statement_pdf(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | float | str | None]:
    # Reconciles a statement against existing activity; it adds no transactions, so
    # allow_reconciled has no effect.
    return RbcDepositImportService(connection, parser=parse_rbc_statement_summary).import_statement(
        account_id, filename, content
    )


def gic_history_account_number(content: bytes, filename: str) -> str:
    return str(
        parse_rbc_gic_transaction_history(pdf_page_texts(open_pdf, content), filename)[
            "account_number"
        ]
    )


def tfsa_account_number(content: bytes, filename: str) -> str:
    return str(
        parse_rbc_tfsa_statement(pdf_page_texts(open_pdf, content), filename)["account_number"]
    )


def deposit_account_number(content: bytes, filename: str) -> str:
    return str(parse_rbc_statement_summary(content, filename)["account_number"])
