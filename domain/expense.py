# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

ExpenseClassification = Literal["required", "discretionary"]
ExpenseSourceKind = Literal["manual", "imported"]
ExpenseAssociationKind = Literal["household", "person", "asset"]


@dataclass(frozen=True, slots=True)
class ExpenseCategory:
    """User-defined factual expense category."""

    id: int
    name: str
    classification: ExpenseClassification
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ExpenseRecord:
    """Factual household expense with period, provenance, and optional association."""

    id: int
    name: str
    category_id: int
    amount: Decimal
    period_start: str
    period_end: str
    source_kind: ExpenseSourceKind
    source_document_id: int | None = None
    association_kind: ExpenseAssociationKind = "household"
    association_id: int | None = None
    created_at: str | None = None
