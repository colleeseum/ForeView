# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FixedTermDeposit:
    """One immutable legacy fixed-term deposit row."""

    id: int
    account_id: int
    name: str
    principal: float
    interest_rate: float
    start_date: str
    maturity_date: str
    maturity_value: float | None
    source_filename: str | None
    redeemable: bool
    renewal_rule: str
