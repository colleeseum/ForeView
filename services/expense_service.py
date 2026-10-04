# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from datetime import date

from domain.expense import ExpenseAssociationKind, ExpenseClassification, ExpenseRecord
from domain.money import MoneyInput
from repositories.expense_repository import ExpenseRepository


class ExpenseService:
    """Transactional application boundary for factual expense workflows."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self.repository = ExpenseRepository(connection)

    def create_category(self, name: str, classification: ExpenseClassification):
        with self._connection:
            return self.repository.create_category(name, classification)

    def create_manual(
        self, *, name: str, category_id: int, amount: MoneyInput,
        period_start: date, period_end: date,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
    ) -> ExpenseRecord:
        with self._connection:
            return self.repository.create_manual_expense(
                name=name, category_id=category_id, amount=amount,
                period_start=period_start, period_end=period_end,
                association_kind=association_kind, association_id=association_id,
            )

    def confirm_import(
        self, *, name: str, category_id: int, amount: MoneyInput,
        period_start: date, period_end: date, source_document_id: int,
        source_name: str, parser_name: str, source_hash: str,
        parser_version: str | None = None,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
    ) -> ExpenseRecord:
        """Create an imported fact only after the caller has confirmed its identity/category."""
        with self._connection:
            return self.repository.create_imported_expense(
                name=name, category_id=category_id, amount=amount,
                period_start=period_start, period_end=period_end,
                source_document_id=source_document_id, source_name=source_name,
                parser_name=parser_name, parser_version=parser_version,
                source_hash=source_hash, association_kind=association_kind,
                association_id=association_id,
            )
