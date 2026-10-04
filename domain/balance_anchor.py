# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BalanceAnchor:
    """Latest known account balance used to rebuild transaction balances."""

    snapshot_date: str
    amount: float
