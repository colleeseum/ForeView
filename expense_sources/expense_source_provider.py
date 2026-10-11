# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Contract for one expense-statement document provider."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from domain.parsed_expense_statement import ParsedExpenseStatement


@dataclass(frozen=True, slots=True)
class ExpenseSourceProvider:
    """Contract implemented by one expense-statement source."""

    key: str
    display_name: str
    parser: Callable[[bytes], ParsedExpenseStatement]
    detects: Callable[[bytes], bool]
    help_text: str
    version: str = "2026.10.06"
    translations: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
