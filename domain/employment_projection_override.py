# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EmploymentProjectionOverride:
    """Optional replacements for one projected employment year."""

    scenario_id: int
    person_id: int
    projection_year: int
    salary: Decimal | None = None
    raise_rate: Decimal | None = None
    rrsp_contribution: Decimal | None = None
    rrsp_deduction: Decimal | None = None
    other_income: Decimal | None = None
