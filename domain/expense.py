# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, TypedDict

ExpenseClassification = Literal["required", "discretionary"]
ExpenseSourceKind = Literal["manual", "imported"]
ExpenseAssociationKind = Literal["household", "person", "account", "real_estate"]
ExpenseOverlapStatus = Literal["clear", "potential", "resolved_include", "resolved_exclude"]
ExpensePeriodKind = Literal["annual_or_one_time", "recurring_statement"]
ExpenseYearStatus = Literal["missing", "needs_resolution", "recorded"]


class ExpenseCategoryTotal(TypedDict):
    category_id: int
    name: str
    classification: ExpenseClassification
    amount: Decimal
    annualized_estimate: Decimal


class ExpenseYearSummary(TypedDict):
    year: int
    status: ExpenseYearStatus
    categories: list[ExpenseCategoryTotal]
    required: Decimal | None
    discretionary: Decimal | None
    total: Decimal | None
    estimated_required: Decimal | None
    estimated_discretionary: Decimal | None
    estimated_total: Decimal | None
    has_partial_coverage: bool
    unresolved_overlaps: list[int]


@dataclass(frozen=True, slots=True)
class ExpenseCategory:
    """User-defined factual expense category."""

    id: int
    name: str
    classification: ExpenseClassification
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ExpenseRecord:
    """Factual household expense with historical classification and provenance."""

    id: int
    identity_id: int
    name: str
    category_id: int
    category_name: str
    classification: ExpenseClassification
    amount: Decimal
    period_start: str
    period_end: str
    source_kind: ExpenseSourceKind
    source_document_id: int | None = None
    source_name: str | None = None
    parser_name: str | None = None
    parser_version: str | None = None
    source_hash: str | None = None
    association_kind: ExpenseAssociationKind = "household"
    association_id: int | None = None
    overlap_status: ExpenseOverlapStatus = "clear"
    period_kind: ExpensePeriodKind = "annual_or_one_time"
    overlap_resolution_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
