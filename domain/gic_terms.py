# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GicTerms:
    """Identity and terms stored on an imported GIC account."""

    account_number: str
    interest_rate: float | None = None
    start_date: str | None = None
    maturity_date: str | None = None
    maturity_value: float | None = None
    principal: float | None = None
    redeemable: bool = False
