# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from calendar import isleap
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from domain.expense import (
    ExpenseAssociationKind,
    ExpenseCategory,
    ExpenseCategoryTotal,
    ExpenseClassification,
    ExpenseOverlapStatus,
    ExpensePeriodKind,
    ExpenseRecord,
    ExpenseYearSummary,
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
        if cursor.lastrowid is None:  # pragma: no cover - SQLite insert invariant
            raise RuntimeError("Created expense category has no identifier")
        return self.get_category(cursor.lastrowid)

    def get_category(self, category_id: int) -> ExpenseCategory:
        row = self._connection.execute(
            "SELECT id, name, classification, is_active FROM expense_categories WHERE id = ?",
            (category_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Expense category {category_id} not found")
        return ExpenseCategory(int(row[0]), str(row[1]), str(row[2]), bool(row[3]))  # type: ignore[arg-type]

    def list_categories(self, *, include_inactive: bool = False) -> list[ExpenseCategory]:
        if include_inactive:
            query = (
                "SELECT id, name, classification, is_active FROM expense_categories ORDER BY name"
            )
        else:
            query = (
                "SELECT id, name, classification, is_active FROM expense_categories "
                "WHERE is_active = 1 ORDER BY name"
            )
        rows = self._connection.execute(query).fetchall()
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
        period_kind: ExpensePeriodKind = "annual_or_one_time",
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
            period_kind=period_kind,
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
        parser_name: str,
        period_kind: ExpensePeriodKind,
        parser_version: str | None = None,
        association_kind: ExpenseAssociationKind = "household",
        association_id: int | None = None,
    ) -> ExpenseRecord:
        if not parser_name.strip():
            raise ValueError("Imported expenses require parser provenance")
        source = self._connection.execute(
            "SELECT filename, file_hash FROM import_batches WHERE id = ?",
            (source_document_id,),
        ).fetchone()
        if source is None:
            raise LookupError(f"Import batch {source_document_id} not found")
        return self._create_expense(
            name=name,
            category_id=category_id,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            source_kind="imported",
            source_document_id=source_document_id,
            source_name=str(source[0]),
            parser_name=parser_name.strip(),
            parser_version=parser_version.strip() if parser_version else None,
            source_hash=str(source[1]),
            association_kind=association_kind,
            association_id=association_id,
            period_kind=period_kind,
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
        period_kind: ExpensePeriodKind,
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
        self._validate_period_kind(period_kind)
        amount_cents = to_cents(amount)
        if amount_cents < 0:
            raise ValueError("Expense amount cannot be negative")
        identity_id = self._get_or_create_identity(
            name, category_id, association_kind, association_id
        )
        overlapping_ids = self._overlapping_ids(
            identity_id,
            period_start,
            period_end,
        )
        overlap_status: ExpenseOverlapStatus = "potential" if overlapping_ids else "clear"
        cursor = self._connection.execute(
            """INSERT INTO expense_records(
                   name, category_id, category_name, classification, amount_cents,
                   period_start, period_end, source_kind, source_document_id, source_name,
                   parser_name, parser_version, source_hash, association_kind, association_id,
                   overlap_status, identity_id, period_kind
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                category_id,
                category.name,
                category.classification,
                amount_cents,
                period_start.isoformat(),
                period_end.isoformat(),
                source_kind,
                source_document_id,
                source_name,
                parser_name,
                parser_version,
                source_hash,
                association_kind,
                association_id,
                overlap_status,
                identity_id,
                period_kind,
            ),
        )
        if cursor.lastrowid is None:  # pragma: no cover - SQLite insert invariant
            raise RuntimeError("Created expense record has no identifier")
        expense_id = cursor.lastrowid
        if overlapping_ids:
            self._connection.executemany(
                """UPDATE expense_records
                      SET overlap_status = 'potential', overlap_resolution_note = NULL
                    WHERE id = ?""",
                ((overlapping_id,) for overlapping_id in overlapping_ids),
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
            raise ValueError("Associated expenses require an association id")
        if association_kind == "person":
            exists = self._connection.execute(
                "SELECT 1 FROM people WHERE id = ?", (association_id,)
            ).fetchone()
        elif association_kind == "account":
            exists = self._connection.execute(
                "SELECT 1 FROM accounts WHERE id = ?", (association_id,)
            ).fetchone()
        elif association_kind == "real_estate":
            exists = self._connection.execute(
                "SELECT 1 FROM real_estate_assets WHERE id = ?", (association_id,)
            ).fetchone()
        else:
            raise ValueError("Invalid expense association kind")
        if exists is None:
            raise ValueError(f"Unknown {association_kind} association {association_id}")

    @staticmethod
    def _validate_period_kind(period_kind: ExpensePeriodKind) -> None:
        if period_kind not in ("annual_or_one_time", "recurring_statement"):
            raise ValueError("Invalid expense period kind")

    def _overlapping_ids(
        self,
        identity_id: int,
        period_start: date,
        period_end: date,
        *,
        exclude_id: int | None = None,
    ) -> list[int]:
        rows = self._connection.execute(
            """SELECT id FROM expense_records
               WHERE identity_id = ?
                 AND period_start <= ? AND period_end >= ?
                 AND (? IS NULL OR id <> ?)
               ORDER BY id""",
            (
                identity_id,
                period_end.isoformat(),
                period_start.isoformat(),
                exclude_id,
                exclude_id,
            ),
        ).fetchall()
        return [int(row[0]) for row in rows]

    def _get_or_create_identity(
        self,
        name: str,
        category_id: int,
        association_kind: ExpenseAssociationKind,
        association_id: int | None,
    ) -> int:
        normalized_name = name.strip()
        row = self._connection.execute(
            """SELECT id FROM expense_identities
                WHERE lower(trim(name)) = lower(trim(?))
                  AND category_id = ? AND association_kind = ? AND association_id IS ?""",
            (normalized_name, category_id, association_kind, association_id),
        ).fetchone()
        if row is not None:
            return int(row[0])
        cursor = self._connection.execute(
            """INSERT INTO expense_identities(
                   name, category_id, association_kind, association_id
               ) VALUES (?, ?, ?, ?)""",
            (normalized_name, category_id, association_kind, association_id),
        )
        if cursor.lastrowid is None:  # pragma: no cover - SQLite insert invariant
            raise RuntimeError("Created expense identity has no identifier")
        return cursor.lastrowid

    def get_expense(self, expense_id: int) -> ExpenseRecord:
        row = self._connection.execute(
            """SELECT id, name, category_id, category_name, classification, amount_cents,
                      period_start, period_end, source_kind, source_document_id, source_name,
                      parser_name, parser_version, source_hash, association_kind, association_id,
                      overlap_status, overlap_resolution_note, created_at, updated_at,
                      identity_id, period_kind
                 FROM expense_records WHERE id = ?""",
            (expense_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Expense record {expense_id} not found")
        return ExpenseRecord(
            id=int(row[0]),
            identity_id=int(row[20]),
            name=str(row[1]),
            category_id=int(row[2]),
            category_name=str(row[3]),
            classification=cast(ExpenseClassification, str(row[4])),
            amount=from_cents(row[5]),
            period_start=str(row[6]),  # type: ignore[arg-type]
            period_end=str(row[7]),
            source_kind=str(row[8]),  # type: ignore[arg-type]
            source_document_id=int(row[9]) if row[9] is not None else None,
            source_name=str(row[10]) if row[10] is not None else None,
            parser_name=str(row[11]) if row[11] is not None else None,
            parser_version=str(row[12]) if row[12] is not None else None,
            source_hash=str(row[13]) if row[13] is not None else None,
            association_kind=str(row[14]),  # type: ignore[arg-type]
            association_id=int(row[15]) if row[15] is not None else None,
            overlap_status=str(row[16]),  # type: ignore[arg-type]
            period_kind=str(row[21]),  # type: ignore[arg-type]
            overlap_resolution_note=str(row[17]) if row[17] is not None else None,
            created_at=str(row[18]),
            updated_at=str(row[19]),
        )

    def list_expenses(self, *, year: int | None = None) -> list[ExpenseRecord]:
        if year is None:
            rows = self._connection.execute(
                "SELECT id FROM expense_records ORDER BY period_start DESC, id DESC"
            ).fetchall()
        else:
            rows = self._connection.execute(
                """SELECT id FROM expense_records
                    WHERE period_start <= ? AND period_end >= ?
                    ORDER BY period_start DESC, id DESC""",
                (f"{year}-12-31", f"{year}-01-01"),
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
        period_kind: ExpensePeriodKind = "annual_or_one_time",
    ) -> ExpenseRecord:
        current = self.get_expense(expense_id)
        if current.source_kind != "manual":
            raise ValueError("Imported expense evidence cannot be edited manually")
        if not name.strip():
            raise ValueError("Expense name is required")
        if period_end < period_start:
            raise ValueError("Expense period end cannot precede start")
        category = self.get_category(category_id)
        if not category.is_active and category_id != current.category_id:
            raise ValueError("Cannot move an expense to an archived category")
        self._validate_association(association_kind, association_id)
        self._validate_period_kind(period_kind)
        amount_cents = to_cents(amount)
        if amount_cents < 0:
            raise ValueError("Expense amount cannot be negative")
        identity_id = self._get_or_create_identity(
            name, category_id, association_kind, association_id
        )
        self._connection.execute(
            """UPDATE expense_records
               SET name = ?, category_id = ?, category_name = ?, classification = ?,
                   amount_cents = ?, period_start = ?, period_end = ?, association_kind = ?,
                   association_id = ?, overlap_status = 'clear',
                   overlap_resolution_note = NULL, identity_id = ?, period_kind = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                name.strip(),
                category_id,
                category.name,
                category.classification,
                amount_cents,
                period_start.isoformat(),
                period_end.isoformat(),
                association_kind,
                association_id,
                identity_id,
                period_kind,
                expense_id,
            ),
        )
        overlapping_ids = self._overlapping_ids(
            identity_id,
            period_start,
            period_end,
            exclude_id=expense_id,
        )
        if overlapping_ids:
            affected_ids = [expense_id, *overlapping_ids]
            self._connection.executemany(
                """UPDATE expense_records
                      SET overlap_status = 'potential', overlap_resolution_note = NULL
                    WHERE id = ?""",
                ((affected_id,) for affected_id in affected_ids),
            )
        self._clear_orphaned_overlap_resolutions()
        return self.get_expense(expense_id)

    def _clear_orphaned_overlap_resolutions(self) -> None:
        self._connection.execute(
            """UPDATE expense_records AS candidate
                  SET overlap_status = 'clear', overlap_resolution_note = NULL
                WHERE candidate.overlap_status <> 'clear'
                  AND NOT EXISTS (
                      SELECT 1 FROM expense_records AS other
                       WHERE other.id <> candidate.id
                         AND other.identity_id = candidate.identity_id
                         AND other.period_start <= candidate.period_end
                         AND other.period_end >= candidate.period_start
                  )"""
        )

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
        if end < year_start or start > year_end:
            return Decimal("0")
        total_days = (end - start).days + 1
        allocations: list[tuple[int, int, int]] = []
        for allocation_year in range(start.year, end.year + 1):
            allocation_start = max(start, date(allocation_year, 1, 1))
            allocation_end = min(end, date(allocation_year, 12, 31))
            allocation_days = (allocation_end - allocation_start).days + 1
            numerator = to_cents(expense.amount) * allocation_days
            allocations.append((allocation_year, numerator // total_days, numerator % total_days))
        remaining = to_cents(expense.amount) - sum(item[1] for item in allocations)
        remainder_order = sorted(allocations, key=lambda item: (-item[2], item[0]))
        extra_years = {item[0] for item in remainder_order[:remaining]}
        allocated_cents = next(
            base_cents + (1 if allocation_year in extra_years else 0)
            for allocation_year, base_cents, _ in allocations
            if allocation_year == year
        )
        return from_cents(allocated_cents)

    def totals_for_year(self, year: int) -> ExpenseYearSummary:
        if year < 1900 or year > 9999:
            raise ValueError("Expense summary year must be between 1900 and 9999")
        records = self.list_expenses(year=year)
        if not records:
            return {
                "year": year,
                "status": "missing",
                "categories": [],
                "required": None,
                "discretionary": None,
                "total": None,
                "estimated_required": None,
                "estimated_discretionary": None,
                "estimated_total": None,
                "has_partial_coverage": False,
                "unresolved_overlaps": [],
            }
        unresolved = [record.id for record in records if record.overlap_status == "potential"]
        if unresolved:
            return {
                "year": year,
                "status": "needs_resolution",
                "categories": [],
                "required": None,
                "discretionary": None,
                "total": None,
                "estimated_required": None,
                "estimated_discretionary": None,
                "estimated_total": None,
                "has_partial_coverage": False,
                "unresolved_overlaps": unresolved,
            }
        included = [record for record in records if record.overlap_status != "resolved_exclude"]
        totals: dict[tuple[int, str, ExpenseClassification], Decimal] = {}
        estimated_totals: dict[tuple[int, str, ExpenseClassification], Decimal] = {}
        records_by_identity_snapshot: dict[
            tuple[int, tuple[int, str, ExpenseClassification]], list[ExpenseRecord]
        ] = {}
        for record in included:
            key = (record.category_id, record.category_name, record.classification)
            totals[key] = totals.get(key, Decimal("0")) + self._amount_for_year(record, year)
            records_by_identity_snapshot.setdefault((record.identity_id, key), []).append(record)
        has_partial_coverage = False
        for (_, key), identity_records in records_by_identity_snapshot.items():
            fixed_records = [
                record for record in identity_records if record.period_kind == "annual_or_one_time"
            ]
            periodic_records = [
                record for record in identity_records if record.period_kind == "recurring_statement"
            ]
            fixed_amount = sum(
                (self._amount_for_year(record, year) for record in fixed_records),
                start=Decimal("0"),
            )
            estimated = fixed_amount
            if periodic_records:
                recorded = sum(
                    (self._amount_for_year(record, year) for record in periodic_records),
                    start=Decimal("0"),
                )
                covered_days = self._covered_days(periodic_records, year)
                year_days = 366 if isleap(year) else 365
                if covered_days < year_days:
                    has_partial_coverage = True
                estimated_cents = (
                    Decimal(to_cents(recorded)) * Decimal(year_days) / Decimal(covered_days)
                ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                estimated += from_cents(int(estimated_cents))
            estimated_totals[key] = estimated_totals.get(key, Decimal("0")) + estimated
        categories: list[ExpenseCategoryTotal] = [
            {
                "category_id": key[0],
                "name": key[1],
                "classification": key[2],  # type: ignore[typeddict-item]
                "amount": amount,
                "annualized_estimate": estimated_totals[key],
            }
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
        estimated_required = sum(
            (
                item["annualized_estimate"]
                for item in categories
                if item["classification"] == "required"
            ),
            start=Decimal("0"),
        )
        estimated_discretionary = sum(
            (
                item["annualized_estimate"]
                for item in categories
                if item["classification"] == "discretionary"
            ),
            start=Decimal("0"),
        )
        return {
            "year": year,
            "status": "recorded",
            "categories": categories,
            "required": required,
            "discretionary": discretionary,
            "total": required + discretionary,
            "estimated_required": estimated_required,
            "estimated_discretionary": estimated_discretionary,
            "estimated_total": estimated_required + estimated_discretionary,
            "has_partial_coverage": has_partial_coverage,
            "unresolved_overlaps": [],
        }

    @staticmethod
    def _covered_days(records: list[ExpenseRecord], year: int) -> int:
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        periods = sorted(
            (
                max(date.fromisoformat(record.period_start), year_start),
                min(date.fromisoformat(record.period_end), year_end),
            )
            for record in records
        )
        merged: list[tuple[date, date]] = []
        for start, end in periods:
            if not merged or start > merged[-1][1] + timedelta(days=1):
                merged.append((start, end))
                continue
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        return sum((end - start).days + 1 for start, end in merged)
