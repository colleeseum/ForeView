# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EmploymentYearPlan:
    """Resolved employment assumptions for one projected calendar year."""

    year: int
    age: int | None
    annual_salary_rate: Decimal
    raise_rate: Decimal | None
    employment_fraction: Decimal
    salary_income: Decimal
    other_income: Decimal
    rrsp_contribution: Decimal
    rrsp_deduction: Decimal
