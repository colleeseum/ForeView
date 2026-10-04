# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PublicPensionEstimate:
    """Official monthly pension estimate under a stated contribution assumption."""

    statement_id: int
    contribution_assumption: str
    activation_age: int
    monthly_amount: Decimal
