# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from domain.expense import (
    ExpenseAssociationKind,
    ExpenseCategory,
    ExpenseClassification,
    ExpenseOverlapStatus,
    ExpenseRecord,
)
from domain.money import MoneyInput, from_cents, to_cents


class ExpenseRepository:
    """Persist factual expense categories and auditable expense records."""

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

    def reclassify_category(
        self, category_id: int, classification: ExpenseClassification
    ) -> ExpenseCategory:
        if classification not in ("required", "discretionary"):
            raise ValueError("Invalid expense classification")
        self.get_category(category_id)
        self._connection.execute(
            "UPDATE expense_categories SET classification = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (classification, category_id),
        )
        return self.get_category(category_id)

    def set_category_active(self, category_id: int, active: bool) -> ExpenseCategory:
        self.get_category(category_id)
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
            source_name=None,
            parser_name=None,
            parser_version=None,
            source_hash=None,
            association_kind=association_kind,
            association_id=association_id,
        )

    def create_imported_expense(
        self,
        *,
        name: str,
        category_id: int,
        amount: MoneyInput,
        period_start: date,
        period_end: date,
        source_document_id: int,
        source_name: str,
        parser_name: str,
        source_hash: str,
        parser_version: str | None = None,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
    ) -> ExpenseRecord:
        if not source_name.strip() or not parser_name.strip() or not source_hash.strip():
            raise ValueError("Imported expenses require source, parser, and source hash provenance")
        return self._create_expense(
            name=name,
            category_id=category_id,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            source_kind="imported",
            source_document_id=source_document_id,
            source_name=source_name.strip(),
            parser_name=parser_name.strip(),
            parser_version=parser_version.strip() if parser_version else None,
            source_hash=source_hash.strip(),
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
        source_name: str | None,
        parser_name: str | None,
        parser_version: str | None,
        source_hash: str | None,
        association_kind: ExpenseAssociationKind,
        association_id: int | None,
    ) -> ExpenseRecord:
        name = name.strip()
        if not name:
            raise ValueError("Expense name is required")
        if period_end < period_start:
            raise ValueError("Expense period end cannot precede start")
        category = self.get_category(category_id)
        if not category.is_active:
            raise ValueError("Cannot add an expense to an archived category")
        self._validate_association(association_kind, association_id)
        amount_cents = to_cents(amount)
        if amount_cents < 0:
            raise ValueError("Expense amount cannot be negative")
        overlap_status: ExpenseOverlapStatus = (
            "potential"
            if self._has_overlap(name, category_id, period_start, period_end, association_kind, association_id)
            else "clear"
        )
        cursor = self._connection.execute(
            """INSERT INTO expense_records(
                   name, category_id, category_name, classification, amount_cents,
                   period_start, period_end, source_kind, source_document_id, source_name,
                   parser_name, parser_version, source_hash, association_kind, association_id,
                   overlap_status
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name, category_id, category.name, category.classification, amount_cents,
                period_start.isoformat(), period_end.isoformat(), source_kind,
                source_document_id, source_name, parser_name, parser_version, source_hash,
                association_kind, association_id, overlap_status,
            ),
        )
        expense_id = int(cursor.lastrowid)
        if overlap_status == "potential":
            self._connection.execute(
                """UPDATE expense_records SET overlap_status = 'potential'
                   WHERE id <> ? AND lower(name) = lower(?) AND category_id = ?
                     AND period_start <= ? AND period_end >= ?
                     AND association_kind = ? AND association_id IS ?
                     AND overlap_status = 'clear'""",
                (expense_id, name, category_id, period_end.isoformat(), period_start.isoformat(),
                 association_kind, association_id),
            )
        return self.get_expense(expense_id)

    def _validate_association(
        self, association_kind: ExpenseAssociationKind, association_id: int | None
    ) -> None:
        if association_kind == "household":
            if association_id is not None:
                raise ValueError("Household expenses cannot have an association id")
            return
        if association_id is None:
            raise ValueError("Person/asset expenses require an association id")
        if association_kind == "person":
            exists = self._connection.execute(
                "SELECT 1 FROM people WHERE id = ?", (association_id,)
            ).fetchone()
        elif association_kind == "asset":
            exists = self._connection.execute(
                """SELECT 1 FROM accounts WHERE id = ?
                   UNION ALL SELECT 1 FROM real_estate_assets WHERE id = ? LIMIT 1""",
                (association_id, association_id),
            ).fetchone()
        else:
            raise ValueError("Invalid expense association kind")
        if exists is None:
            raise ValueError(f"Unknown {association_kind} association {association_id}")

    def _has_overlap(
        self,
        name: str,
        category_id: int,
        period_start: date,
        period_end: date,
        association_kind: ExpenseAssociationKind,
        association_id: int | None,
    ) -> bool:
        return self._connection.execute(
            """SELECT 1 FROM expense_records
               WHERE lower(name) = lower(?) AND category_id = ?
                 AND period_start <= ? AND period_end >= ?
                 AND association_kind = ? AND association_id IS ?
                 AND overlap_status <> 'resolved_exclude' LIMIT 1""",
            (name, category_id, period_end.isoformat(), period_start.isoformat(),
             association_kind, association_id),
        ).fetchone() is not None

    def get_expense(self, expense_id: int) -> ExpenseRecord:
        row = self._connection.execute(
            """SELECT id, name, category_id, category_name, classification, amount_cents,
                      period_start, period_end, source_kind, source_document_id, source_name,
                      parser_name, parser_version, source_hash, association_kind, association_id,
                      overlap_status, overlap_resolution_note, created_at, updated_at
                 FROM expense_records WHERE id = ?""",
            (expense_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Expense record {expense_id} not found")
        return ExpenseRecord(
            id=int(row[0]), name=str(row[1]), category_id=int(row[2]), category_name=str(row[3]),
            classification=str(row[4]), amount=from_cents(row[5]), period_start=str(row[6]),  # type: ignore[arg-type]
            period_end=str(row[7]), source_kind=str(row[8]),  # type: ignore[arg-type]
            source_document_id=int(row[9]) if row[9] is not None else None,
            source_name=str(row[10]) if row[10] is not None else None,
            parser_name=str(row[11]) if row[11] is not None else None,
            parser_version=str(row[12]) if row[12] is not None else None,
            source_hash=str(row[13]) if row[13] is not None else None,
            association_kind=str(row[14]),  # type: ignore[arg-type]
            association_id=int(row[15]) if row[15] is not None else None,
            overlap_status=str(row[16]),  # type: ignore[arg-type]
            overlap_resolution_note=str(row[17]) if row[17] is not None else None,
            created_at=str(row[18]), updated_at=str(row[19]),
        )

    def list_expenses(self, *, year: int | None = None) -> list[ExpenseRecord]:
        where = ""
        parameters: tuple[object, ...] = ()
        if year is not None:
            where = " WHERE period_start <= ? AND period_end >= ?"
            parameters = (f"{year}-12-31", f"{year}-01-01")
        rows = self._connection.execute(
            f"SELECT id FROM expense_records{where} ORDER BY period_start DESC, id DESC", parameters
        ).fetchall()
        return [self.get_expense(int(row[0])) for row in rows]

    def update_expense(
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
    ) -> ExpenseRecord:
        current = self.get_expense(expense_id)
        if not name.strip():
            raise ValueError("Expense name is required")
        if period_end < period_start:
            raise ValueError("Expense period end cannot precede start")
        category = self.get_category(category_id)
        if not category.is_active and category_id != current.category_id:
            raise ValueError("Cannot move an expense to an archived category")
        self._validate_association(association_kind, association_id)
        self._connection.execute(
            """UPDATE expense_records
               SET name = ?, category_id = ?, category_name = ?, classification = ?,
                   amount_cents = ?, period_start = ?, period_end = ?, association_kind = ?,
                   association_id = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (name.strip(), category_id, category.name, category.classification, to_cents(amount),
             period_start.isoformat(), period_end.isoformat(), association_kind, association_id,
             expense_id),
        )
        return self.get_expense(expense_id)

    def resolve_overlap(self, expense_id: int, *, include: bool, note: str) -> ExpenseRecord:
        if not note.strip():
            raise ValueError("Overlap resolution requires an audit note")
        self.get_expense(expense_id)
        status = "resolved_include" if include else "resolved_exclude"
        self._connection.execute(
            """UPDATE expense_records
               SET overlap_status = ?, overlap_resolution_note = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, note.strip(), expense_id),
        )
        return self.get_expense(expense_id)

    @staticmethod
    def _amount_for_year(expense: ExpenseRecord, year: int) -> Decimal:
        start = date.fromisoformat(expense.period_start)
        end = date.fromisoformat(expense.period_end)
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        overlap_start = max(start, year_start)
        overlap_end = min(end, year_end)
        if overlap_end < overlap_start:
            return Decimal("0")
        total_days = (end - start).days + 1
        overlap_days = (overlap_end - overlap_start).days + 1
        return (expense.amount * Decimal(overlap_days) / Decimal(total_days)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def totals_for_year(self, year: int) -> dict[str, object]:
        records = self.list_expenses(year=year)
        if not records:
            return {"year": year, "status": "missing", "categories": [],
                    "required": None, "discretionary": None, "total": None,
                    "unresolved_overlaps": []}
        unresolved = [record.id for record in records if record.overlap_status == "potential"]
        included = [record for record in records if record.overlap_status != "resolved_exclude"]
        totals: dict[tuple[int, str, str], Decimal] = {}
        for record in included:
            key = (record.category_id, record.category_name, record.classification)
            totals[key] = totals.get(key, Decimal("0")) + self._amount_for_year(record, year)
        categories = [
            {"category_id": key[0], "name": key[1], "classification": key[2], "amount": amount}
            for key, amount in sorted(totals.items(), key=lambda item: item[0][1].lower())
        ]
        required = sum(
            (item["amount"] for item in categories if item["classification"] == "required"),
            start=Decimal("0"),
        )
        discretionary = sum(
            (item["amount"] for item in categories if item["classification"] == "discretionary"),
            start=Decimal("0"),
        )
        return {"year": year, "status": "needs_resolution" if unresolved else "recorded",
                "categories": categories, "required": required, "discretionary": discretionary,
                "total": required + discretionary, "unresolved_overlaps": unresolved}
