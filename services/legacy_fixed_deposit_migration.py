"""Convert legacy fixed-term deposits into linked GIC accounts."""

from __future__ import annotations

import re
import sqlite3

from domain.gic_terms import GicTerms
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.fixed_term_deposit_repository import FixedTermDepositRepository


class LegacyFixedDepositMigration:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._accounts = AccountRepository(connection)
        self._deposits = FixedTermDepositRepository(connection)
        self._ownership = AccountOwnershipRepository(connection)

    def execute(self) -> int:
        migrated = 0
        for deposit in self._deposits.list_all():
            parent = self._accounts.get(deposit.account_id)
            if parent is None:
                continue
            certificate_match = re.search(r"(?:#|\s)(\d+)$", deposit.name)
            certificate_pattern = f"%{certificate_match.group(1)}%" if certificate_match else None
            existing = self._accounts.find_gic_child(
                deposit.account_id,
                name=deposit.name,
                certificate_pattern=certificate_pattern,
                principal=deposit.principal,
                start_date=deposit.start_date,
            )
            if existing:
                continue
            child_id = self._accounts.create_gic_child(
                parent,
                deposit.name,
                GicTerms(
                    account_number=f"gic:{deposit.account_id}:{deposit.name}",
                    interest_rate=deposit.interest_rate,
                    start_date=deposit.start_date,
                    maturity_date=deposit.maturity_date,
                    maturity_value=deposit.maturity_value,
                    principal=deposit.principal,
                ),
            )
            self._ownership.copy(deposit.account_id, child_id)
            migrated += 1
        return migrated
