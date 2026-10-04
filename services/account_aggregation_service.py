"""Aggregate account read models without double-counting linked assets."""

from __future__ import annotations

from typing import cast

from account_types import account_type_registry
from domain.money import MoneyInput, as_decimal


class AccountAggregationService:
    def category_totals(self, accounts: list[dict[str, object]]) -> list[dict[str, object]]:
        result = []
        for provider in account_type_registry().providers:
            account_type, label = provider.key, provider.display_name
            items = [item for item in accounts if item.get("account_type") == account_type]
            parents = [item for item in items if not item.get("parent_account_id")]
            total = sum(
                (
                    as_decimal(cast(MoneyInput, parent.get("rollup_amount") or 0))
                    for parent in parents
                ),
                start=as_decimal(0),
            )
            result.append(
                {
                    "type": account_type,
                    "label": label,
                    "total": float(total),
                    "count": len(parents),
                    "gic_count": sum(item.get("asset_kind") == "gic" for item in items),
                }
            )
        return result
