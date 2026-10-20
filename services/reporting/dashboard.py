# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from account_types import account_type_registry
from domain.money import as_decimal

SAVINGS_RATE_THRESHOLD = 0.025


def build_dashboard_summary(
    accounts: Sequence[Mapping[str, Any]],
    categories: Sequence[Mapping[str, Any]],
    holdings: Sequence[Mapping[str, Any]],
    real_estate: Sequence[Mapping[str, Any]],
    transactions: Sequence[Mapping[str, Any]],
    *,
    savings_threshold: float = SAVINGS_RATE_THRESHOLD,
    holds_securities: Callable[[str | None], bool] = lambda _institution: False,
) -> dict[str, Any]:
    """Build the dashboard read model without depending on Flask or SQLite."""
    parents = [account for account in accounts if not account.get("parent_account_id")]
    zero = as_decimal(0)
    immovable_value = sum(
        (as_decimal(item.get("estimated_value") or 0) for item in real_estate), start=zero
    )
    gross_assets = (
        sum((as_decimal(item["total"]) for item in categories), start=zero) + immovable_value
    )
    invested_value = sum(
        (as_decimal(item.get("market_value") or 0) for item in holdings), start=zero
    )
    gic_value = sum(
        (
            as_decimal(item.get("latest_amount") or item.get("principal") or 0)
            for item in accounts
            if item.get("asset_kind") == "gic"
        ),
        start=zero,
    )
    type_registry = account_type_registry()
    liquidity_by_type = {provider.key: zero for provider in type_registry.providers}
    low_rate_value = zero
    low_rate_accounts: list[dict[str, Any]] = []
    uninvested_security_accounts: list[dict[str, Any]] = []

    for parent in parents:
        parent_id = int(parent["id"])
        children = [item for item in accounts if item.get("parent_account_id") == parent_id]
        child_gic_value = sum(
            (
                as_decimal(item.get("latest_amount") or item.get("principal") or 0)
                for item in children
                if item.get("asset_kind") == "gic"
            ),
            start=zero,
        )
        parent_holdings = sum(
            (
                as_decimal(item.get("market_value") or 0)
                for item in holdings
                if int(item["account_id"]) == parent_id
            ),
            start=zero,
        )
        account_value = as_decimal(parent.get("latest_amount") or 0)
        base_value = (
            account_value - child_gic_value
            if parent.get("balance_includes_children")
            else account_value
        )
        uninvested = max(zero, base_value - parent_holdings)
        redeemable_gics = sum(
            (
                as_decimal(item.get("latest_amount") or item.get("principal") or 0)
                for item in children
                if item.get("asset_kind") == "gic" and item.get("redeemable")
            ),
            start=zero,
        )
        account_type = parent.get("account_type")
        provider = type_registry.find(str(account_type) if account_type is not None else None)
        if provider and provider.liquidity_class == "liquid":
            liquidity_by_type[provider.key] += uninvested + redeemable_gics
        if (
            parent.get("asset_kind") == "account"
            and parent.get("interest_rate") is not None
            and Decimal(str(parent["interest_rate"])) < Decimal(str(savings_threshold))
        ):
            low_rate_value += account_value
            low_rate_accounts.append(
                {
                    "institution": parent.get("institution"),
                    "account_number": parent.get("account_number"),
                    "name": parent.get("name"),
                    "account_type": parent.get("account_type"),
                    "rate": float(parent["interest_rate"]),
                    "amount": float(account_value),
                }
            )
        if holds_securities(parent.get("institution")) and uninvested > 0.01:
            uninvested_security_accounts.append(
                {
                    "institution": parent.get("institution"),
                    "account_number": parent.get("account_number"),
                    "name": parent.get("name"),
                    "account_type": parent.get("account_type"),
                    "amount": float(uninvested),
                }
            )

    serialized_liquidity = {key: float(value) for key, value in liquidity_by_type.items()}
    return {
        "gross_assets": float(gross_assets),
        "immovable_value": float(immovable_value),
        "invested_value": float(invested_value),
        "gic_value": float(gic_value),
        "liquidity_value": float(
            sum(
                (
                    value
                    for key, value in liquidity_by_type.items()
                    if type_registry.get(key).liquidity_class == "liquid"
                ),
                start=zero,
            )
        ),
        "rrsp_uninvested": float(liquidity_by_type.get("rrsp", zero)),
        "uninvested_security_value": float(
            sum(
                (as_decimal(item["amount"]) for item in uninvested_security_accounts),
                start=zero,
            )
        ),
        "uninvested_security_accounts": uninvested_security_accounts,
        "liquidity_by_type": serialized_liquidity,
        "low_rate_value": float(low_rate_value),
        "low_rate_accounts": low_rate_accounts,
        "savings_threshold": savings_threshold,
        "categories": list(categories),
        "maturities": [
            {
                "name": item.get("name"),
                "institution": item.get("institution"),
                "maturity_date": item.get("maturity_date"),
                "amount": item.get("maturity_value") or item.get("latest_amount"),
            }
            for item in accounts
            if item.get("asset_kind") == "gic" and item.get("maturity_date")
        ],
        "recent_transactions": sorted(
            transactions,
            key=lambda item: (item.get("transaction_date") or "", item.get("id") or 0),
            reverse=True,
        )[:12],
    }
