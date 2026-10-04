from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from flask import jsonify, request

from account_types import account_type_registry
from domain.money import as_decimal
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from services.account_aggregation_service import AccountAggregationService
from services.account_summary_query import AccountSummaryQuery
from services.fixed_term_deposit_creation_service import FixedTermDepositCreationService
from services.transaction_service import TransactionService
from web.dependencies import dependency
from web.model_blueprint import blueprint
from web.route_values import payload_bool


@blueprint.get("/api/model/accounts")
def model_accounts():
    with dependency("connect")() as connection:
        accounts = AccountSummaryQuery(connection).execute()
        return jsonify(
            {
                "accounts": accounts,
                "category_totals": AccountAggregationService().category_totals(accounts),
                "account_types": [
                    {"key": item.key, "display_name": item.display_name}
                    for item in account_type_registry().providers
                ],
            }
        )


def _rate(payload: dict[str, Any]) -> float | None:
    value = payload.get("interest_rate")
    return float(str(value)) / 100 if value not in (None, "") else None


@blueprint.post("/api/model/accounts")
def add_account_route():
    payload = request.get_json(silent=True) or {}
    try:
        owners = [
            (int(item["person_id"]), float(item["share"])) for item in payload.get("owners", [])
        ]
        with dependency("connect")() as connection:
            if payload.get("asset_kind") == "gic" and not owners:
                parent_id = int(payload["parent_account_id"])
                owners = [
                    (ownership.person_id, ownership.share)
                    for ownership in AccountOwnershipRepository(connection).list_for_account(
                        parent_id
                    )
                ]
            account = AccountRepository(connection).create(
                payload.get("name"),
                str(payload["category"]),
                account_number=str(payload["account_number"]),
                institution=payload.get("institution"),
                external_provider=payload.get("external_provider") or None,
                external_account_id=payload.get("external_account_id") or None,
                asset_kind=str(payload.get("asset_kind", "account")),
                parent_account_id=int(payload["parent_account_id"])
                if payload.get("parent_account_id") not in (None, "")
                else None,
                start_date=payload.get("start_date") or None,
                maturity_date=payload.get("maturity_date") or None,
                maturity_value=as_decimal(payload["maturity_value"])
                if payload.get("maturity_value") not in (None, "")
                else None,
                principal=as_decimal(payload["principal"])
                if payload.get("principal") not in (None, "")
                else None,
                redeemable=payload_bool(payload.get("redeemable", False)),
            )
            AccountOwnershipRepository(connection).replace(account.id, owners)
            current_rate = _rate(payload)
            if current_rate is not None:
                AccountRepository(connection).set_current_interest_rate(account.id, current_rate)
            if payload.get("balance_amount") not in (None, ""):
                BalanceSnapshotRepository(connection).add(
                    account.id,
                    str(payload.get("balance_date") or date.today().isoformat()),
                    as_decimal(payload["balance_amount"]),
                    current_rate,
                )
                TransactionService(connection).recalculate_balances(account.id)
        return jsonify({"id": account.id}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.put("/api/model/accounts/<int:account_id>")
def update_account_route(account_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            previous = AccountRepository(connection).get(account_id)
            AccountRepository(connection).update(
                account_id,
                name=payload.get("name"),
                account_number=str(payload["account_number"]),
                institution=payload.get("institution"),
                external_provider=payload.get("external_provider") or None,
                external_account_id=payload.get("external_account_id") or None,
                category=payload.get("category"),
                asset_kind=payload.get("asset_kind"),
                parent_account_id=int(payload["parent_account_id"])
                if payload.get("parent_account_id") not in (None, "")
                else None,
                start_date=payload.get("start_date") or None,
                maturity_date=payload.get("maturity_date") or None,
                maturity_value=as_decimal(payload["maturity_value"])
                if payload.get("maturity_value") not in (None, "")
                else None,
                principal=as_decimal(payload["principal"])
                if payload.get("principal") not in (None, "")
                else None,
                redeemable=payload_bool(payload.get("redeemable", False)),
            )
            if "owners" in payload:
                AccountOwnershipRepository(connection).replace(
                    account_id,
                    [(int(item["person_id"]), float(item["share"])) for item in payload["owners"]],
                )
            elif (
                payload.get("asset_kind") == "gic"
                and previous
                and previous.parent_account_id != int(payload["parent_account_id"])
            ):
                new_parent_owners = AccountOwnershipRepository(connection).list_for_account(
                    int(payload["parent_account_id"])
                )
                AccountOwnershipRepository(connection).replace(
                    account_id,
                    [(ownership.person_id, ownership.share) for ownership in new_parent_owners],
                )
            current_rate = _rate(payload)
            if current_rate is not None:
                AccountRepository(connection).set_current_interest_rate(account_id, current_rate)
            if payload.get("balance_amount") not in (None, ""):
                BalanceSnapshotRepository(connection).add(
                    account_id,
                    str(payload.get("balance_date") or date.today().isoformat()),
                    as_decimal(payload["balance_amount"]),
                    current_rate,
                )
                TransactionService(connection).recalculate_balances(account_id)
        return jsonify({"updated": True})
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/model/accounts/<int:account_id>/balance")
def add_balance_route(account_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            current_rate = _rate(payload)
            BalanceSnapshotRepository(connection).add(
                account_id,
                str(payload["date"]),
                as_decimal(payload["amount"]),
                current_rate,
            )
            if current_rate is not None:
                AccountRepository(connection).set_current_interest_rate(account_id, current_rate)
        return jsonify({"saved": True}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400


@blueprint.post("/api/model/accounts/<int:account_id>/gics")
def add_gic_route(account_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        with dependency("connect")() as connection:
            deposit = FixedTermDepositCreationService(connection).create(
                account_id,
                str(payload["name"]),
                as_decimal(payload["principal"]),
                float(payload["interest_rate"]),
                str(payload["start_date"]),
                str(payload["maturity_date"]),
                redeemable=bool(payload.get("redeemable", False)),
                renewal_rule=str(payload.get("renewal_rule", "cash_at_maturity")),
            )
        return jsonify({"id": deposit.id}), 201
    except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as error:
        return jsonify({"error": str(error)}), 400
