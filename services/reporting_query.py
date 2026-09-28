"""Read model for factual reports exposed by the model API."""

from __future__ import annotations

import sqlite3

from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.investment_holding_repository import InvestmentHoldingRepository


class ReportingQuery:
    """Collect read-only reports without exposing repositories to web routes."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._balances = BalanceSnapshotRepository(connection)
        self._imports = ImportBatchRepository(connection)
        self._holdings = InvestmentHoldingRepository(connection)

    def import_history(
        self,
        account_id: int | None = None,
        account_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        return self._imports.history(account_id, account_type, limit)

    def holdings(
        self, account_id: int | None = None, account_type: str | None = None
    ) -> list[dict[str, object]]:
        return self._holdings.latest(account_id, account_type)

    def annual_summary(self) -> list[dict[str, object]]:
        return self._balances.annual_totals()
