"""Reconciliation workflow for RBC deposit statements."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from ingestion.statement_import import account_digits, content_hash, unrecognized_pdf
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.statement_reconciliation_repository import StatementReconciliationRepository
from repositories.transaction_repository import TransactionRepository
from services.reconciliation_checkpoint_service import ReconciliationCheckpointService
from services.transaction_service import TransactionService

StatementParser = Callable[[bytes, str], dict[str, Any]]


class RbcDepositImportService:
    """Reconcile one RBC monthly statement against imported transactions."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        parser: StatementParser,
    ) -> None:
        self._connection = connection
        self._parser = parser
        self._accounts = AccountRepository(connection)
        self._batches = ImportBatchRepository(connection)
        self._reconciliations = StatementReconciliationRepository(connection)
        self._snapshots = BalanceSnapshotRepository(connection)
        self._transactions = TransactionService(connection)
        self._transaction_rows = TransactionRepository(connection)

    def import_statement(
        self, account_id: int, filename: str, content: bytes
    ) -> dict[str, int | float | str | None]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        if existing:
            reconciliation = self._reconciliations.get_by_import_batch(existing.id)
            if reconciliation and reconciliation.closing_balance is not None:
                self._store_closing_balance(
                    reconciliation.account_id,
                    reconciliation.statement_end,
                    reconciliation.closing_balance,
                    filename,
                )
                self._transactions.recalculate_balances(reconciliation.account_id)
            return {
                "batch_id": existing.id,
                "imported": 0,
                "duplicates": existing.row_count,
                "status": "already_reconciled",
                "reconciliation_status": reconciliation.status if reconciliation else None,
            }

        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError("Account not found")
        try:
            summary = self._parser(content, filename)
        except ValueError as error:
            raise unrecognized_pdf("RBC") from error
        if account_digits(summary["account_number"]) != account_digits(account.account_number):
            raise ValueError(f"{filename} belongs to a different account")

        transaction_amounts = self._transaction_rows.amounts_between(
            account_id, summary["statement_start"], summary["statement_end"]
        )
        csv_net_change = round(sum(transaction_amounts), 2)
        difference = round(
            float(summary["opening_balance"]) + csv_net_change - float(summary["closing_balance"]),
            2,
        )
        status = (
            "reconciled"
            if transaction_amounts and abs(difference) <= 0.01
            else ("no_matching_transactions" if not transaction_amounts else "difference")
        )
        with self._connection:
            batch_id = self._batches.create(
                account_id, filename, file_hash, len(transaction_amounts)
            ).id
            reconciliation_id = self._reconciliations.create(
                account_id,
                batch_id,
                summary["statement_start"],
                summary["statement_end"],
                opening_balance=summary["opening_balance"],
                closing_balance=summary["closing_balance"],
                statement_deposits=summary["statement_deposits"],
                statement_withdrawals=summary["statement_withdrawals"],
                csv_transaction_count=len(transaction_amounts),
                csv_net_change=csv_net_change,
                difference=difference,
                status=status,
            ).id
            self._store_closing_balance(
                account_id,
                summary["statement_end"],
                float(summary["closing_balance"]),
                filename,
            )
            if status == "reconciled":
                ReconciliationCheckpointService(self._connection).record_statement(
                    account_id,
                    summary["statement_start"],
                    summary["statement_end"],
                    float(summary["closing_balance"]),
                )
            self._transactions.recalculate_balances(account_id)
        return {
            "batch_id": batch_id,
            "reconciliation_id": reconciliation_id,
            "imported": 0,
            "duplicates": 0,
            "status": "reconciled",
            "reconciliation_status": status,
            "csv_transaction_count": len(transaction_amounts),
            "difference": difference,
        }

    def _store_closing_balance(
        self, account_id: int, statement_end: str, closing_balance: float, filename: str
    ) -> None:
        self._snapshots.add(
            account_id,
            statement_end,
            closing_balance,
            source_sheet="RBC PDF reconciliation",
            source_address=filename,
        )
