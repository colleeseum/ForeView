"""Read model for the application dashboard."""

from __future__ import annotations

import sqlite3
from typing import Any

from institution_support.registry import institution_registry
from repositories.investment_holding_repository import InvestmentHoldingRepository
from services.account_aggregation_service import AccountAggregationService
from services.account_summary_query import AccountSummaryQuery
from services.dashboard import build_dashboard_summary
from services.real_estate_summary_query import RealEstateSummaryQuery
from services.transaction_service import TransactionService


class DashboardQuery:
    """Assemble the complete dashboard read model from factual query sources."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def execute(self) -> dict[str, Any]:
        accounts = AccountSummaryQuery(self._connection).execute()
        categories = AccountAggregationService().category_totals(accounts)
        holdings = InvestmentHoldingRepository(self._connection).latest()
        real_estate = RealEstateSummaryQuery(self._connection).execute()
        transactions = TransactionService(self._connection).summary(limit=12)
        return build_dashboard_summary(
            accounts,
            categories,
            holdings,
            real_estate,
            transactions,
            holds_securities=institution_registry().holds_securities,
        )
