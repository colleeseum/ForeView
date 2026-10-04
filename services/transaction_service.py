# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from datetime import date
from decimal import Decimal
from typing import Any, cast

from domain.balance_recalculation_row import BalanceRecalculationRow
from domain.money import MoneyInput, as_decimal
from ingestion.raw_sources import has_bank_reported_balance
from institution_support.registry import institution_registry
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.transaction_repository import TransactionRepository
from services.reconciliation_checkpoint_service import ReconciliationCheckpointService


class TransactionService:
    """Apply balance, roll-up, opening-balance, and reconciliation rules."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        statement_sources: Collection[str] | None = None,
    ) -> None:
        self._connection = connection
        self._statement_sources = (
            institution_registry().statement_sources()
            if statement_sources is None
            else statement_sources
        )
        self._transactions = TransactionRepository(connection)
        self._snapshots = BalanceSnapshotRepository(connection)
        self._accounts = AccountRepository(connection)

    def recalculate_balances(self, account_id: int) -> int:
        anchor = self._transactions.latest_snapshot(account_id)
        if not anchor:
            return 0
        rows = self._balance_rows(account_id)
        if not rows or rows[0].transaction_date > anchor.snapshot_date:
            return 0
        running = as_decimal(anchor.amount)
        updated = 0
        for row in rows:
            stored = row.balance_after
            if stored is not None and has_bank_reported_balance(
                row.raw_data, self._statement_sources
            ):
                running = as_decimal(stored)
            else:
                self._transactions.set_balance(row.id, float(running))
                updated += 1
            running -= as_decimal(row.amount)
        return updated

    def _balance_rows(self, account_id: int) -> list[BalanceRecalculationRow]:
        """An account's rows that take part in balance rebuilding, newest first."""
        account = self._accounts.get(account_id)
        provider = (
            institution_registry().find(account.institution)
            if account is not None and account.institution
            else None
        )
        excluded_sources = institution_registry().balance_excluded_sources()
        include_excluded = bool(
            account
            and (
                account.balance_includes_children
                or (
                    provider
                    and self._transactions.has_snapshot_source(
                        account_id, provider.balance_including_snapshot_sources
                    )
                )
            )
        )
        # Rows are ordered newest first, so only the first can follow the anchor.
        return self._transactions.rows_for_balance_recalculation(
            account_id,
            excluded_sources,
            include_excluded=include_excluded,
        )

    def _undo_manual_reconciliation(self, account_id: int, reconciliation_date: str) -> None:
        """Remove an earlier reconciliation of a date and the balances derived from it.

        Calculated balances are cleared and rebuilt from the remaining anchors, so
        a new reconciliation of the date is compared with the ledger as it stood
        before the earlier one, not with the earlier reconciled amount.
        """
        if not self._snapshots.remove_manual_reconciliation(account_id, reconciliation_date):
            return
        for row in self._balance_rows(account_id):
            if not has_bank_reported_balance(row.raw_data, self._statement_sources):
                self._transactions.clear_balance(row.id)
        self.recalculate_balances(account_id)
        ReconciliationCheckpointService(self._connection).withdraw_known_balance(
            account_id, reconciliation_date
        )

    def summary(
        self,
        account_id: int | None = None,
        account_type: str | None = None,
        limit: int = 250,
    ) -> list[dict[str, object]]:
        result = self._transactions.summary_rows(account_id, account_type)
        if account_id is None:
            account_ids = self._transactions.scoped_account_ids(account_type)
            events: dict[int, list[tuple[tuple[str, int], MoneyInput]]] = {
                scoped_id: [] for scoped_id in account_ids
            }
            for (
                identifier,
                event_account,
                value_date,
                amount,
            ) in self._transactions.balance_events():
                if event_account in events:
                    events[event_account].append(((value_date, identifier), amount))
            for account_events in events.values():
                account_events.sort(key=lambda event: event[0])
            pointers = {scoped_id: 0 for scoped_id in account_ids}
            balances: dict[int, Decimal] = {}
            for item in result:
                row_key = (str(item["transaction_date"]), int(cast(Any, item["id"])))
                for scoped_id in account_ids:
                    account_events = events[scoped_id]
                    while (
                        pointers[scoped_id] < len(account_events)
                        and account_events[pointers[scoped_id]][0] <= row_key
                    ):
                        balances[scoped_id] = as_decimal(account_events[pointers[scoped_id]][1])
                        pointers[scoped_id] += 1
                item["combined_balance_after"] = (
                    float(sum(balances.values(), start=as_decimal(0))) if balances else None
                )
            if result:
                latest = {
                    scoped_id: account_events[-1][1]
                    for scoped_id, account_events in events.items()
                    if account_events
                }
                running_total = (
                    sum((as_decimal(value) for value in latest.values()), start=as_decimal(0))
                    if latest
                    else None
                )
                for item in reversed(result):
                    item["combined_balance_after"] = (
                        float(running_total) if running_total is not None else None
                    )
                    if running_total is not None and not (
                        item["asset_kind"] == "gic" and item["parent_balance_includes_children"]
                    ):
                        running_total -= as_decimal(cast(MoneyInput, item["amount"]))
        return list(reversed(result[-limit:]))

    def opening_balances(
        self, account_id: int | None = None, account_type: str | None = None
    ) -> list[dict[str, object]]:
        transactions = self.summary(account_id, account_type, limit=100000)
        first_by_account: dict[int, dict[str, object]] = {}
        for item in transactions:
            item_account_id = int(cast(Any, item["account_id"]))
            current = first_by_account.get(item_account_id)
            item_key = (str(item["transaction_date"]), int(cast(Any, item["id"])))
            if current is None or item_key < (
                str(current["transaction_date"]),
                int(cast(Any, current["id"])),
            ):
                first_by_account[item_account_id] = item

        openings: list[dict[str, object]] = []
        for item_account_id, item in first_by_account.items():
            if item["balance_after"] is None:
                continue
            opening = as_decimal(cast(MoneyInput, item["balance_after"])) - as_decimal(
                cast(MoneyInput, item["amount"])
            )
            combined = item.get("combined_balance_after")
            if combined is not None and not (
                item["asset_kind"] == "gic" and item["parent_balance_includes_children"]
            ):
                combined = float(
                    as_decimal(cast(MoneyInput, combined))
                    - as_decimal(cast(MoneyInput, item["amount"]))
                )
            openings.append(
                {
                    **item,
                    "id": f"opening-{item_account_id}",
                    "amount": 0.0,
                    "description": "Opening balance",
                    "balance_after": float(opening),
                    "combined_balance_after": combined,
                    "category": None,
                    "transaction_type": "opening_balance",
                    "is_opening_balance": True,
                }
            )

        include_children = bool(
            account_id is not None
            and self._transactions.account_asset_kind(account_id) == "account"
        )
        for row in self._transactions.first_snapshot_rows(
            account_id, account_type, include_children
        ):
            if row["account_id"] in first_by_account:
                continue
            openings.append(
                {
                    "id": f"opening-{row['account_id']}",
                    "transaction_date": row["snapshot_date"],
                    "amount": 0.0,
                    "description": "Opening balance",
                    "balance_after": float(row["amount"]),
                    "combined_balance_after": None,
                    "category": None,
                    "transaction_type": "opening_balance",
                    "is_opening_balance": True,
                    **{
                        key: row[key]
                        for key in (
                            "account_id",
                            "account_number",
                            "institution",
                            "account_name",
                            "asset_kind",
                            "parent_account_id",
                            "parent_name",
                            "parent_account_number",
                            "parent_institution",
                            "parent_balance_includes_children",
                        )
                    },
                }
            )
        return openings

    def reconcile(
        self, account_id: int, reconciliation_date: str, known_balance: MoneyInput
    ) -> dict[str, object]:
        if as_decimal(known_balance) < 0:
            raise ValueError("Reconciliation balance cannot be negative")
        try:
            date.fromisoformat(reconciliation_date)
        except ValueError as error:
            raise ValueError(f"Invalid reconciliation date: {reconciliation_date}") from error
        if not self._transactions.account_exists(account_id):
            raise ValueError("Account not found")
        self._undo_manual_reconciliation(account_id, reconciliation_date)
        previous = self._transactions.latest_known_balance(account_id, reconciliation_date)
        previous_balance = previous[1] if previous else None
        difference = (
            float(as_decimal(known_balance) - as_decimal(previous_balance))
            if previous_balance is not None
            else None
        )
        self._snapshots.add(
            account_id,
            reconciliation_date,
            known_balance,
            source_sheet="Manual reconciliation",
            source_address="transactions",
        )
        updated = self.recalculate_balances(account_id)
        status = "reconciled" if difference in (None, 0.0) else "adjusted"
        checkpoint = (
            ReconciliationCheckpointService(self._connection).record_known_balance(
                account_id, reconciliation_date, known_balance
            )
            if status == "reconciled"
            else None
        )
        return {
            "account_id": account_id,
            "date": reconciliation_date,
            "known_balance": known_balance,
            "previous_balance": previous_balance,
            "difference": difference,
            "updated_transactions": updated,
            "status": status,
            "reconciled_through": checkpoint.reconciled_through if checkpoint else None,
        }
