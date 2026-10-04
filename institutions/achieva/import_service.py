# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Persistence workflow for Achieva GIC statements."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from ingestion.pdf_document import PdfOpener, pdf_page_texts
from ingestion.statement_import import already_imported, content_hash, unrecognized_pdf
from ingestion.statement_row_writer import StatementRowWriter
from institutions.achieva import raw_sources
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository

StatementParser = Callable[[Iterable[str], str], dict[str, Any]]


class AchievaImportService:
    """Import one Achieva GIC statement into its linked account tree."""

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
        self._ownership = AccountOwnershipRepository(connection)
        self._snapshots = BalanceSnapshotRepository(connection)
        self._batches = ImportBatchRepository(connection)
        self._rows = StatementRowWriter(connection, allow_reconciled=allow_reconciled)

    def import_gic(
        self, parent_account_id: int, filename: str, content: bytes
    ) -> dict[str, int | float | str | None]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        if existing:
            return already_imported(existing)
        selected = self._accounts.get(parent_account_id)
        if selected and selected.asset_kind == "gic" and selected.parent_account_id is not None:
            parent_account_id = selected.parent_account_id
        parent = self._accounts.get(parent_account_id)
        if parent is None:
            raise ValueError("Parent account not found")
        parsed = self._parse(content, filename)
        child_id = self._find_child(parent_account_id, str(parsed["name"]))
        if child_id is None:
            child = self._accounts.create(
                str(parsed["name"]),
                parent.account_type,
                account_number="",
                institution=parent.institution,
                tax_treatment=parent.tax_treatment,
                asset_kind="gic",
                parent_account_id=parent_account_id,
                start_date=parsed["start_date"],
                principal=parsed["principal"],
            )
            child_id = child.id
            owners = self._ownership.list_for_account(parent_account_id)
            self._ownership.replace(child_id, [(owner.person_id, owner.share) for owner in owners])
        rows = parsed["rows"]
        with self._connection:
            self._accounts.set_current_interest_rate(child_id, None)
            self._snapshots.add(
                child_id,
                parsed["statement_date"],
                float(parsed["closing_value"]),
                lock_date=parsed["start_date"],
                source_sheet="Achieva GIC PDF",
                source_address=filename,
            )
            batch_id = self._batches.create(child_id, filename, file_hash, len(rows)).id
            imported = self._rows.write(
                batch_id, child_id, rows, source=raw_sources.ACHIEVA_GIC_PDF
            ).imported
            self._batches.update_row_count(batch_id, imported)
        return {
            "batch_id": batch_id,
            "imported": imported,
            "duplicates": len(rows) - imported,
            "status": "imported",
            "document_type": "gic",
            "gic_name": parsed["name"],
        }

    def _parse(self, content: bytes, filename: str) -> dict[str, Any]:
        try:
            return self._parser(pdf_page_texts(self._pdf_opener, content), filename)
        except ValueError as error:
            raise unrecognized_pdf("Achieva") from error

    def _find_child(self, parent_account_id: int, parsed_name: str) -> int | None:
        parsed_key = self._name_key(parsed_name)
        for child in self._accounts.gic_children(parent_account_id):
            child_key = self._name_key(str(child.name))
            if child_key in parsed_key or parsed_key in child_key:
                return child.id
        return None

    @staticmethod
    def _name_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())
