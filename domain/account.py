# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Account:
    """One immutable row from the accounts table."""

    id: int
    name: str | None
    account_number: str | None
    account_type: str
    institution: str | None
    tax_treatment: str
    current_interest_rate: float | None
    asset_kind: str
    parent_account_id: int | None
    balance_includes_children: bool
    start_date: str | None
    maturity_date: str | None
    maturity_value: float | None
    principal: float | None
    redeemable: bool
    external_provider: str | None
    external_account_id: str | None
