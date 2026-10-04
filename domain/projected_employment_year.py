# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProjectedEmploymentYear:
    """Calculated annual employment, contribution, tax and disposable income."""

    year: int
    age: int | None
    annual_salary_rate: Decimal
    raise_rate: Decimal | None
    employment_fraction: Decimal
    salary_income: Decimal
    other_income: Decimal
    gross_income: Decimal
    rrsp_contribution: Decimal
    rrsp_deduction: Decimal
    cpp_qpp: Decimal
    ei: Decimal
    qpip: Decimal
    federal_tax: Decimal
    quebec_tax: Decimal
    net_income_after_tax: Decimal
    disposable_income: Decimal
    rule_year: int
    rules_held_constant: bool
