# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass

from domain.consolidated_income_value import ConsolidatedIncomeValue


@dataclass(frozen=True, slots=True)
class IncomeTaxSnapshot:
    """Resolved annual facts for the newest tax year at the user's disposal."""

    tax_year: int
    available_years: tuple[int, ...]
    values: tuple[ConsolidatedIncomeValue, ...]
