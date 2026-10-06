# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Preview and confirm expense statements through registered source providers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from domain.expense import ExpenseAssociationKind, ExpensePeriodKind, ExpenseRecord
from expense_sources.expense_source_provider import ExpenseSourceProvider
from expense_sources.registry import ExpenseSourceRegistry, expense_source_registry
from ingestion.statement_import import content_hash
from repositories.expense_repository import ExpenseRepository
from repositories.import_batch_repository import ImportBatchRepository


@dataclass(frozen=True, slots=True)
class ExpenseImportPreview:
    """Reviewable evidence extracted from an expense statement."""

    provider_key: str
    provider_display_name: str
    parser_version: str
    suggested_identity: str
    amount: Decimal
    period_start: date
    period_end: date
    period_kind: ExpensePeriodKind
    source_filename: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_key": self.provider_key,
            "provider_display_name": self.provider_display_name,
            "parser_version": self.parser_version,
            "suggested_identity": self.suggested_identity,
            "amount": f"{self.amount:.2f}",
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_kind": self.period_kind,
            "source_filename": self.source_filename,
        }


class ExpenseImportService:
    """Coordinate PDF detection, review, and transactional confirmation."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        registry: ExpenseSourceRegistry = expense_source_registry,
    ) -> None:
        self._connection = connection
        self._registry = registry
        self._expenses = ExpenseRepository(connection)
        self._batches = ImportBatchRepository(connection)

    def preview(
        self,
        content: bytes,
        source_filename: str = "uploaded.pdf",
        provider_key: str | None = None,
    ) -> ExpenseImportPreview:
        """Parse a PDF without writing an import batch or expense record."""

        provider = self._provider_for(content, provider_key)
        parsed = provider.parser(content)
        return ExpenseImportPreview(
            provider_key=provider.key,
            provider_display_name=provider.display_name,
            parser_version=provider.version,
            suggested_identity=parsed.suggested_identity,
            amount=parsed.amount,
            period_start=parsed.period_start,
            period_end=parsed.period_end,
            period_kind=parsed.period_kind,
            source_filename=source_filename,
        )

    def confirm(
        self,
        *,
        content: bytes,
        source_filename: str,
        provider_key: str,
        name: str,
        category_id: int,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
    ) -> ExpenseRecord:
        """Re-parse trusted evidence and atomically persist an imported expense."""

        provider = self._provider_for(content, provider_key)
        parsed = provider.parser(content)
        with self._connection:
            batch = self._batches.get_or_create(
                account_id=None,
                filename=source_filename,
                file_hash=content_hash(content),
                row_count=1,
            )
            return self._expenses.create_imported_expense(
                name=name,
                category_id=category_id,
                amount=parsed.amount,
                period_start=parsed.period_start,
                period_end=parsed.period_end,
                source_document_id=batch.id,
                parser_name=provider.key,
                parser_version=provider.version,
                association_kind=association_kind,
                association_id=association_id,
                period_kind=parsed.period_kind,
            )

    def _provider_for(self, content: bytes, provider_key: str | None) -> ExpenseSourceProvider:
        provider = (
            self._registry.get(provider_key) if provider_key else self._registry.detect(content)
        )
        if not provider.detects(content):
            raise ValueError(
                f"The PDF does not match the expected format for {provider.display_name}"
            )
        return provider
