# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Typed result returned by an expense-statement parser."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain.expense import ExpensePeriodKind


@dataclass(frozen=True, slots=True)
class ParsedExpenseStatement:
    """Extracted evidence from one expense-statement PDF.

    The provider must return only the amount attributable to the current
    billing period and the actual service-period start/end dates.  Prior
    balances, payments, outstanding amounts, or total-due figures that
    bundle other periods are rejected.
    """

    suggested_identity: str
    """Human-friendly name such as "Hydro" for use as an expense identity."""

    amount: Decimal
    """Current-period expense amount in dollars, represented exactly."""

    period_start: date
    """First calendar day represented by the recurring expense evidence."""

    period_end: date
    """Last calendar day represented by the recurring expense evidence."""

    period_kind: ExpensePeriodKind
    """Whether the statement covers a recurring billing period or not."""
