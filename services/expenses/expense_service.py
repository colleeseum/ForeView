# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import date

from domain.expense import (
    ExpenseAssociationKind,
    ExpenseCategory,
    ExpenseClassification,
    ExpensePeriodKind,
    ExpenseRecord,
)
from domain.money import MoneyInput
from domain.validation_error import ValidationError
from repositories.expense_repository import ExpenseRepository
from repositories.import_batch_repository import ImportBatchRepository


class ExpenseService:
    """Transactional application boundary for factual expense workflows."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self.repository = ExpenseRepository(connection)

    def create_category(self, name: str, classification: ExpenseClassification) -> ExpenseCategory:
        with self._connection:
            return self.repository.create_category(name, classification)

    def update_category(
        self,
        category_id: int,
        *,
        name: str,
        classification: ExpenseClassification,
        active: bool,
    ) -> ExpenseCategory:
        with self._connection:
            self.repository.rename_category(category_id, name)
            self.repository.reclassify_category(category_id, classification)
            return self.repository.set_category_active(category_id, active)

    def create_manual(
        self,
        *,
        name: str,
        category_id: int,
        amount: MoneyInput,
        period_start: date,
        period_end: date,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
        period_kind: ExpensePeriodKind = "annual_or_one_time",
    ) -> ExpenseRecord:
        with self._connection:
            return self.repository.create_manual_expense(
                name=name,
                category_id=category_id,
                amount=amount,
                period_start=period_start,
                period_end=period_end,
                association_kind=association_kind,
                association_id=association_id,
                period_kind=period_kind,
            )

    def confirm_import(
        self,
        *,
        name: str,
        category_id: int,
        amount: MoneyInput,
        period_start: date,
        period_end: date,
        source_document_id: int,
        parser_name: str,
        period_kind: ExpensePeriodKind,
        parser_version: str | None = None,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
    ) -> ExpenseRecord:
        """Create an imported fact only after the caller has confirmed its identity/category."""
        with self._connection:
            return self.repository.create_imported_expense(
                name=name,
                category_id=category_id,
                amount=amount,
                period_start=period_start,
                period_end=period_end,
                source_document_id=source_document_id,
                parser_name=parser_name,
                parser_version=parser_version,
                association_kind=association_kind,
                association_id=association_id,
                period_kind=period_kind,
            )

    def update_manual(
        self,
        expense_id: int,
        *,
        name: str,
        category_id: int,
        amount: MoneyInput,
        period_start: date,
        period_end: date,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
        period_kind: ExpensePeriodKind = "annual_or_one_time",
    ) -> ExpenseRecord:
        with self._connection:
            return self.repository.update_expense(
                expense_id,
                name=name,
                category_id=category_id,
                amount=amount,
                period_start=period_start,
                period_end=period_end,
                association_kind=association_kind,
                association_id=association_id,
                period_kind=period_kind,
            )

    def resolve_overlap(self, expense_id: int, *, include: bool, note: str) -> ExpenseRecord:
        with self._connection:
            return self.repository.resolve_overlap(expense_id, include=include, note=note)

    @staticmethod
    def deletion_token(record: ExpenseRecord) -> str:
        """Guard the exact evidence shown in a destructive confirmation."""
        return hashlib.sha256(
            json.dumps(asdict(record), sort_keys=True, default=str).encode()
        ).hexdigest()

    def delete_expense(self, expense_id: int, *, expected_token: str) -> None:
        with self._connection:
            # Acquire the writer lock before reading evidence or checking provenance.
            self.repository.lock_for_deletion(expense_id)
            record = self.repository.get_expense(expense_id)
            if self.deletion_token(record) != expected_token:
                raise ValidationError(
                    "expense_delete_stale",
                    "The expense changed. Refresh the page before deleting it.",
                )
            self.repository.delete_expense(expense_id)
            if record.source_document_id is not None:
                ImportBatchRepository(self._connection).delete_if_unreferenced(
                    record.source_document_id
                )
