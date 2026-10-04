# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

ExpenseClassification = Literal["required", "discretionary"]
ExpenseSourceKind = Literal["manual", "imported"]
ExpenseAssociationKind = Literal["household", "person", "asset"]
ExpenseOverlapStatus = Literal["clear", "potential", "resolved_include", "resolved_exclude"]


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
    overlap_resolution_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
