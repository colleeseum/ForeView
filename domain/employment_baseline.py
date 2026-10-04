# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EmploymentBaseline:
    """A factual annual salary rate effective on a specific date."""

    id: int
    person_id: int
    effective_date: str
    annual_salary: Decimal
    province_of_employment: str
    payroll_plan: str
    source: str | None
