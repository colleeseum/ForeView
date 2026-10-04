# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from datetime import date

from domain.expense import ExpenseCategory, ExpenseRecord, ExpenseAssociationKind, ExpenseClassification
from domain.money import MoneyInput, from_cents, to_cents


class ExpenseRepository:
    """Persist factual expense categories and records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_category(self, name: str, classification: ExpenseClassification) -> ExpenseCategory:
        name = name.strip()
        if not name:
            raise ValueError("Expense category name is required")
        if classification not in ("required", "discretionary"):
            raise ValueError("Invalid expense classification")
        cursor = self._connection.execute(
            "INSERT INTO expense_categories(name, classification) VALUES (?, ?)",
            (name, classification),
        )
        return self.get_category(int(cursor.lastrowid))

    def get_category(self, category_id: int) -> ExpenseCategory:
        row = self._connection.execute(
            "SELECT id, name, classification, is_active FROM expense_categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Expense category {category_id} not found")
        return ExpenseCategory(int(row[0]), str(row[1]), str(row[2]), bool(row[3]))  # type: ignore[arg-type]

    def list_categories(self, *, include_inactive: bool = False) -> list[ExpenseCategory]:
        where = "" if include_inactive else " WHERE is_active = 1"
        rows = self._connection.execute(
            f"SELECT id, name, classification, is_active FROM expense_categories{where} ORDER BY name"
        ).fetchall()
        return [ExpenseCategory(int(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in rows]  # type: ignore[arg-type]

    def rename_category(self, category_id: int, name: str) -> ExpenseCategory:
        name = name.strip()
        if not name:
            raise ValueError("Expense category name is required")
        self._connection.execute(
            "UPDATE expense_categories SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name, category_id),
        )
        return self.get_category(category_id)

    def set_category_active(self, category_id: int, active: bool) -> ExpenseCategory:
        self._connection.execute(
            "UPDATE expense_categories SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(active), category_id),
        )
        return self.get_category(category_id)

    def create_manual_expense(
        self,
        *,
        name: str,
        category_id: int,
        amount: MoneyInput,
        period_start: date,
        period_end: date,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
    ) -> ExpenseRecord:
        return self._create_expense(
            name=name,
            category_id=category_id,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            source_kind="manual",
            source_document_id=None,
            association_kind=association_kind,
            association_id=association_id,
        )

    def _create_expense(
        self,
        *,
        name: str,
        category_id: int,
        amount: MoneyInput,
        period_start: date,
        period_end: date,
        source_kind: str,
        source_document_id: int | None,
        association_kind: ExpenseAssociationKind,
        association_id: int | None,
    ) -> ExpenseRecord:
        name = name.strip()
        if not name:
            raise ValueError("Expense name is required")
        if period_end < period_start:
            raise ValueError("Expense period end cannot precede start")
        if association_kind == "household" and association_id is not None:
            raise ValueError("Household expenses cannot have an association id")
        if association_kind != "household" and association_id is None:
            raise ValueError("Person/asset expenses require an association id")
        self.get_category(category_id)
        amount_cents = to_cents(amount)
        if amount_cents < 0:
            raise ValueError("Expense amount cannot be negative")
        cursor = self._connection.execute(
            """INSERT INTO expense_records(
                   name, category_id, amount_cents, period_start, period_end,
                   source_kind, source_document_id, association_kind, association_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                category_id,
                amount_cents,
                period_start.isoformat(),
                period_end.isoformat(),
                source_kind,
                source_document_id,
                association_kind,
                association_id,
            ),
        )
        return self.get_expense(int(cursor.lastrowid))

    def get_expense(self, expense_id: int) -> ExpenseRecord:
        row = self._connection.execute(
            """SELECT id, name, category_id, amount_cents, period_start, period_end,
                      source_kind, source_document_id, association_kind, association_id, created_at
                 FROM expense_records WHERE id = ?""",
            (expense_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Expense record {expense_id} not found")
        return ExpenseRecord(
            id=int(row[0]), name=str(row[1]), category_id=int(row[2]), amount=from_cents(row[3]),
            period_start=str(row[4]), period_end=str(row[5]), source_kind=str(row[6]),  # type: ignore[arg-type]
            source_document_id=int(row[7]) if row[7] is not None else None,
            association_kind=str(row[8]), association_id=int(row[9]) if row[9] is not None else None,  # type: ignore[arg-type]
            created_at=str(row[10]),
        )

    def totals_for_year(self, year: int) -> dict[str, object]:
        rows = self._connection.execute(
            """SELECT c.id, c.name, c.classification, COALESCE(SUM(e.amount_cents), 0)
                 FROM expense_categories c
                 JOIN expense_records e ON e.category_id = c.id
                WHERE e.period_start <= ? AND e.period_end >= ?
                GROUP BY c.id, c.name, c.classification
                ORDER BY c.name""",
            (f"{year}-12-31", f"{year}-01-01"),
        ).fetchall()
        categories = [
            {"category_id": int(r[0]), "name": str(r[1]), "classification": str(r[2]), "amount": from_cents(r[3])}
            for r in rows
        ]
        required = sum((c["amount"] for c in categories if c["classification"] == "required"), start=from_cents(0))
        discretionary = sum((c["amount"] for c in categories if c["classification"] == "discretionary"), start=from_cents(0))
        return {"year": year, "categories": categories, "required": required, "discretionary": discretionary, "total": required + discretionary}
