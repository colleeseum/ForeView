# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.fixed_term_deposit import FixedTermDeposit
from domain.gic_terms import GicTerms
from domain.money import MoneyInput
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.fixed_term_deposit_repository import FixedTermDepositRepository


class FixedTermDepositCreationService:
    """Create a legacy deposit row and its visible child GIC account together."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._accounts = AccountRepository(connection)
        self._deposits = FixedTermDepositRepository(connection)
        self._ownership = AccountOwnershipRepository(connection)

    def create(
        self,
        parent_account_id: int,
        name: str,
        principal: MoneyInput,
        interest_rate: float,
        start_date: str,
        maturity_date: str,
        *,
        redeemable: bool = False,
        renewal_rule: str = "cash_at_maturity",
    ) -> FixedTermDeposit:
        parent = self._accounts.get(parent_account_id)
        if parent is None:
            raise ValueError("Parent account does not exist")
        deposit = self._deposits.create(
            parent_account_id,
            name,
            principal,
            interest_rate,
            start_date,
            maturity_date,
            redeemable=redeemable,
            renewal_rule=renewal_rule,
        )
        child_id = self._accounts.create_gic_child(
            parent,
            deposit.name,
            GicTerms(
                account_number=f"gic:{parent_account_id}:{deposit.name}",
                interest_rate=deposit.interest_rate,
                start_date=deposit.start_date,
                maturity_date=deposit.maturity_date,
                maturity_value=deposit.maturity_value,
                principal=deposit.principal,
                redeemable=deposit.redeemable,
            ),
        )
        self._ownership.copy(parent_account_id, child_id)
        return deposit
