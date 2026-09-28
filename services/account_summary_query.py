"""Read model for account balances, ownership, and linked assets."""

from __future__ import annotations

import sqlite3
from typing import cast

from domain.money import MoneyInput, as_decimal
from repositories.account_repository import AccountRepository


class AccountSummaryQuery:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def execute(self) -> list[dict[str, object]]:
        accounts = AccountRepository(self._connection).summary_rows()
        children_by_parent: dict[int, list[dict[str, object]]] = {}
        for account in accounts:
            parent_id = account.get("parent_account_id")
            if parent_id is not None:
                children_by_parent.setdefault(int(parent_id), []).append(account)
        for account in accounts:
            direct_amount = account.get("latest_amount")
            children = children_by_parent.get(int(account["id"]), [])
            child_total = sum(
                (
                    as_decimal(cast(MoneyInput, child.get("latest_amount") or 0))
                    for child in children
                ),
                start=as_decimal(0),
            )
            rollup_amount = as_decimal(cast(MoneyInput, direct_amount or 0))
            if children and not account.get("balance_includes_children"):
                rollup_amount += child_total
            account["rollup_amount"] = (
                float(rollup_amount) if direct_amount is not None or children else None
            )
            account["non_gic_amount"] = (
                float(
                    as_decimal(cast(MoneyInput, direct_amount or 0)) - child_total
                    if account.get("balance_includes_children")
                    else as_decimal(cast(MoneyInput, direct_amount or 0))
                )
                if children
                else None
            )
        return accounts
