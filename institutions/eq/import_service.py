# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Persistence workflow for EQ Bank PDF statements."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from ingestion.pdf_document import PdfOpener, pdf_page_texts
from ingestion.statement_import import (
    account_digits,
    already_imported,
    content_hash,
    unrecognized_pdf,
)
from ingestion.statement_row_writer import StatementRowWriter
from institutions.eq import raw_sources
from repositories.account_repository import AccountRepository
from repositories.import_batch_repository import ImportBatchRepository

StatementParser = Callable[[Iterable[str], str], tuple[str | None, list[dict[str, Any]]]]


class EqImportService:
    """Import an EQ statement while retaining every original transaction row."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        parser: StatementParser,
        pdf_opener: PdfOpener,
        allow_reconciled: bool = False,
    ) -> None:
        self._connection = connection
        self._parser = parser
        self._pdf_opener = pdf_opener
        self._accounts = AccountRepository(connection)
        self._batches = ImportBatchRepository(connection)
        self._rows = StatementRowWriter(connection, allow_reconciled=allow_reconciled)

    def import_statement(
        self, account_id: int, filename: str, content: bytes
    ) -> dict[str, int | str]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        if existing:
            return already_imported(existing)
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError("Account not found")
        statement_account, rows = self._parse(content, filename, account.institution or "unknown")
        expected_account = account_digits(account.account_number)
        if statement_account and expected_account and statement_account != expected_account:
            raise ValueError(f"{filename} belongs to a different account")
        with self._connection:
            batch_id = self._batches.create(account_id, filename, file_hash).id
            counts = self._rows.write(batch_id, account_id, rows, source=raw_sources.EQ_PDF)
            self._batches.update_row_count(batch_id, counts.imported)
        return {
            "batch_id": batch_id,
            "imported": counts.imported,
            "duplicates": counts.duplicates,
            "status": "imported",
        }

    def _parse(
        self, content: bytes, filename: str, institution: str
    ) -> tuple[str | None, list[dict[str, Any]]]:
        pages = pdf_page_texts(self._pdf_opener, content)
        try:
            return self._parser(pages, filename)
        except ValueError as error:
            raise unrecognized_pdf(institution) from error
