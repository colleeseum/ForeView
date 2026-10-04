# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BalanceSnapshot:
    """One immutable observed account balance."""

    id: int
    account_id: int
    snapshot_date: str
    amount: float
    contribution: float | None
    lock_date: str | None
    maturity_date: str | None
    interest_rate: float | None
    source_sheet: str
    source_address: str
