# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import urllib.parse
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from domain.questrade_authorization import QuestradeAuthorization
from ingestion.reconciled_period_guard import ReconciledPeriodGuard
from repositories.account_repository import AccountRepository
from repositories.activity_sync_state_repository import ActivitySyncStateRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.investment_holding_repository import InvestmentHoldingRepository
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from repositories.raw_transaction_repository import RawTransactionRepository
from repositories.transaction_repository import TransactionRepository
from services.transaction_service import TransactionService

from .unauthorized import QuestradeUnauthorized

ApiGetter = Callable[[QuestradeAuthorization, str], dict[str, Any]]

# Questrade answers at most 31 days of activity per request.
WINDOW = timedelta(days=30)
# How far back an account's first sync reaches without a configured history_start.
DEFAULT_HISTORY = timedelta(days=490)
# Each later sync re-reads at least this much before the previous one ended, to pick
# up activity Questrade posted late with an earlier date; known rows are deduplicated.
# When the gap since that sync is short, it re-reads a full WINDOW instead, since one
# request costs the same either way.
LOOKBACK = timedelta(days=7)


def _start_of_day(value: str, setting: str) -> datetime:
    try:
        start = date.fromisoformat(value)
    except ValueError as error:
        raise RuntimeError(
            f"Questrade {setting} must be a YYYY-MM-DD date, not {value!r}"
        ) from error
    return datetime.combine(start, time.min, tzinfo=UTC)


def _first_sync_start(history_start: str | None) -> datetime:
    if not history_start:
        return datetime.now(UTC) - DEFAULT_HISTORY
    return _start_of_day(history_start, "history_start")


def sync_questrade_connection(
    connect: Callable[[], sqlite3.Connection],
    connection_name: str,
    *,
    api_getter: ApiGetter,
    refresh_expiring: Callable[[sqlite3.Connection], None],
    refresh_authorization: Callable[[sqlite3.Connection, QuestradeAuthorization], None],
    history_start: str | None = None,
    fetch_from: str | None = None,
) -> dict[str, Any]:
    """Pull accounts, balances, positions, and activity for one Questrade login.

    Activity is fetched incrementally, up to now, from whichever is earlier: ``LOOKBACK``
    before where the previous sync of each account stopped, or one ``WINDOW`` ago. An account's first sync starts at
    ``history_start`` (YYYY-MM-DD) or, without one, ``DEFAULT_HISTORY`` ago.

    ``fetch_from`` (YYYY-MM-DD) re-fetches every account of this login from that date
    instead, for example to recover activity missing from a reconciled period.
    """
    first_sync_start = _first_sync_start(history_start)
    requested_start = _start_of_day(fetch_from, "fetch_from") if fetch_from else None
    with connect() as connection:
        account_repository = AccountRepository(connection)
        authorizations = QuestradeAuthorizationRepository(connection)
        batch_repository = ImportBatchRepository(connection)
        holding_repository = InvestmentHoldingRepository(connection)
        raw_transactions = RawTransactionRepository(connection)
        snapshots = BalanceSnapshotRepository(connection)
        transactions = TransactionRepository(connection)
        sync_state = ActivitySyncStateRepository(connection)
        # A sync is not interactive: activity entering a reconciled period is stored
        # and the period is rechecked, then flagged for review if it no longer matches.
        reconciled_periods = ReconciledPeriodGuard(connection, allow=True)
        periods_needing_review = 0
        stored = authorizations.get_by_name(connection_name)
        if stored is None:
            raise RuntimeError(f"Questrade connection '{connection_name}' is not connected")
        attempted_at = datetime.now(UTC).isoformat(timespec="seconds")
        authorizations.mark_attempted(connection_name, attempted_at)
        connection.commit()
        try:
            refresh_expiring(connection)
        except RuntimeError as error:
            authorizations.mark_failed(connection_name, attempted_at, str(error))
            connection.commit()
            raise
        stored = authorizations.get_by_name(connection_name)
        if stored is None:
            raise RuntimeError(f"Questrade connection '{connection_name}' is not connected")
        authorization: QuestradeAuthorization = stored
        component_errors: list[dict[str, str]] = []

        def record_error(account_number: str, component: str, error: RuntimeError) -> None:
            component_errors.append(
                {"account": account_number, "component": component, "error": str(error)}
            )

        def api_get(path: str) -> dict[str, Any]:
            nonlocal authorization
            try:
                return api_getter(authorization, path)
            except QuestradeUnauthorized:
                refresh_authorization(connection, authorization)
                refreshed = authorizations.get_by_name(connection_name)
                if refreshed is None:
                    raise
                authorization = refreshed
                return api_getter(authorization, path)

        try:
            accounts_data = api_get("/v1/accounts")
        except RuntimeError as error:
            authorizations.mark_failed(connection_name, attempted_at, str(error))
            connection.commit()
            raise
        accounts = accounts_data.get("accounts", [])
        position_count = 0
        execution_count = 0
        balance_count = 0
        transaction_count = 0
        valuation_date = date.today().isoformat()
        for account in accounts:
            number = account.get("number")
            if not number:
                continue
            account_number = str(number)
            type_name = str(account.get("type", "")).lower()
            account_type = (
                "tfsa"
                if "tfsa" in type_name
                else ("rrsp" if "rrsp" in type_name else "non_registered")
            )
            local_account = account_repository.find_by_external_id(
                "questrade", account_number
            ) or account_repository.find_by_institution_number("Questrade", account_number)
            if local_account:
                account_id = local_account.id
                account_repository.link_external(
                    account_id,
                    institution="Questrade",
                    provider="questrade",
                    external_account_id=account_number,
                    account_type=account_type,
                )
            else:
                account_id = account_repository.create(
                    f"Questrade {account_number}",
                    account_type,
                    account_number=account_number,
                    institution="Questrade",
                    external_provider="questrade",
                    external_account_id=account_number,
                ).id
            try:
                balances = api_get(
                    f"/v1/accounts/{urllib.parse.quote(account_number, safe='')}/balances"
                )
                combined = balances.get("combinedBalances", [])
                if combined:
                    preferred = next(
                        (item for item in combined if item.get("currency") == "CAD"), combined[0]
                    )
                    amount = preferred.get("totalEquity")
                    if amount is not None:
                        snapshots.record_reported(
                            account_id,
                            valuation_date,
                            float(amount),
                            source_sheet="Questrade",
                            source_address=f"account:{account_number}",
                        )
                        balance_count += 1
            except RuntimeError as error:
                record_error(account_number, "balances", error)
            try:
                positions = api_get(
                    f"/v1/accounts/{urllib.parse.quote(account_number, safe='')}/positions"
                )
                source_filename = f"questrade:{connection_name}:{account_number}:{valuation_date}"
                holding_repository.delete_for_account_source_prefix(account_id, "questrade:")
                for position in positions.get("positions", []):
                    symbol = str(position.get("symbol") or position.get("symbolId") or "Unknown")
                    holding_repository.upsert(
                        account_id,
                        valuation_date,
                        "Security",
                        symbol,
                        symbol,
                        float(position.get("openQuantity") or 0),
                        float(position.get("currentPrice") or 0),
                        float(position.get("currentMarketValue") or 0),
                        None,
                        source_filename,
                    )
                position_count += len(positions.get("positions", []))
            except RuntimeError as error:
                record_error(account_number, "positions", error)
            activity_end = datetime.now(UTC)
            synced_until = sync_state.synced_until(account_id)
            if requested_start is not None:
                activity_start = requested_start
            elif synced_until is not None:
                activity_start = min(synced_until - LOOKBACK, activity_end - WINDOW)
            else:
                activity_start = first_sync_start
            try:
                # Executions are only counted; the API answers at most one window.
                start_time = max(activity_start, activity_end - WINDOW).isoformat()
                end_time = activity_end.isoformat()
                executions = api_get(
                    f"/v1/accounts/{urllib.parse.quote(account_number, safe='')}/executions?"
                    f"{urllib.parse.urlencode({'startTime': start_time, 'endTime': end_time})}"
                )
                execution_count += len(executions.get("executions", []))
            except RuntimeError as error:
                record_error(account_number, "executions", error)
            try:
                # One activity batch per Questrade account, whichever login syncs it.
                activity_batch_hash = f"questrade:{account_number}:activities"
                batch_id = batch_repository.get_or_create(
                    account_id,
                    f"Questrade activities {account_number}",
                    activity_batch_hash,
                ).id
                next_row_number = raw_transactions.next_row_number(batch_id)
                window_start = activity_start
                while window_start < activity_end:
                    window_end = min(window_start + WINDOW, activity_end)
                    activities = api_get(
                        f"/v1/accounts/{urllib.parse.quote(account_number, safe='')}/activities?"
                        f"{urllib.parse.urlencode({'startTime': window_start.isoformat(), 'endTime': window_end.isoformat()})}"
                    ).get("activities", [])
                    for activity in activities:
                        raw_data = json.dumps(
                            {
                                "source": "questrade",
                                "connection": connection_name,
                                "activity": activity,
                            },
                            sort_keys=True,
                        )
                        # An activity is identified by its own content (timestamps, amounts,
                        # symbol), not by the login that fetched it.
                        activity_hash = hashlib.sha256(
                            json.dumps(activity, sort_keys=True).encode()
                        ).hexdigest()
                        raw_id = raw_transactions.id_for_hash(batch_id, activity_hash)
                        if raw_id is None:
                            raw_id = raw_transactions.add(
                                batch_id, next_row_number, activity_hash, raw_data
                            )
                            next_row_number += 1
                        timestamp = str(
                            activity.get("transactionDate")
                            or activity.get("tradeDate")
                            or valuation_date
                        )
                        transaction_date = timestamp[:10]
                        amount = activity.get("netAmount")
                        if amount is None:
                            continue
                        activity_type = str(activity.get("type") or "Unclassified")
                        symbol = str(activity.get("symbol") or "").strip()
                        description = str(
                            activity.get("description") or f"{activity_type} {symbol}"
                        ).strip()
                        gross_amount = activity.get("grossAmount")
                        reinvested = (
                            "reinvest"
                            in f"{activity_type} {activity.get('action', '')} {description}".lower()
                        )
                        if reinvested and float(amount or 0) == 0 and gross_amount is not None:
                            amount = gross_amount
                        if reinvested and float(amount or 0) == 0:
                            value_match = re.search(r"\$([0-9,]+(?:\.[0-9]+)?)", description)
                            if value_match:
                                amount = float(value_match.group(1).replace(",", ""))
                        existing_transaction = transactions.id_for_raw_transaction(raw_id)
                        if existing_transaction is not None:
                            transactions.update_details(
                                existing_transaction,
                                transaction_date=transaction_date,
                                amount=float(amount),
                                description=description,
                                category=activity_type,
                                transaction_type=activity_type.lower(),
                            )
                        else:
                            reconciled_periods.admit(account_id, transaction_date)
                            transactions.create(
                                account_id,
                                transaction_date,
                                float(amount),
                                raw_transaction_id=raw_id,
                                description=description,
                                category=activity_type,
                                transaction_type=activity_type.lower(),
                            )
                            transaction_count += 1
                    window_start = window_end
                batch_repository.update_row_count_from_transactions(batch_id)
                # Only a fully fetched range moves the watermark.
                sync_state.record(account_id, activity_end)
            except RuntimeError as error:
                record_error(account_number, "activities", error)
            periods_needing_review += len(reconciled_periods.finish())
            transactions.clear_balances_from_source(account_id, "questrade")
            TransactionService(connection).recalculate_balances(account_id)
        synced_at = datetime.now(UTC).isoformat(timespec="seconds")
        if component_errors:
            summary = "; ".join(
                f"{item['account']} {item['component']}: {item['error']}"
                for item in component_errors
            )
            authorizations.mark_failed(connection_name, attempted_at, summary)
        else:
            authorizations.mark_synced(connection_name, synced_at)
        connection.commit()
    return {
        "connection": connection_name,
        "status": "partial" if component_errors else "success",
        "attempted_at": attempted_at,
        "synced_at": None if component_errors else synced_at,
        "errors": component_errors,
        "account_count": len(accounts),
        "balance_count": balance_count,
        "position_count": position_count,
        "execution_count": execution_count,
        "transaction_count": transaction_count,
        "reconciled_periods_needing_review": periods_needing_review,
    }
