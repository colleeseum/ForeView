# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.investment_holding import InvestmentHolding
from domain.money import from_cents, to_cents


class InvestmentHoldingRepository:
    """Persist and retrieve dated investment positions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        account_id: int,
        valuation_date: str,
        asset_class: str | None,
        fund_code: str,
        fund_name: str,
        units: float,
        unit_price: float,
        market_value: float,
        allocation_pct: float | None,
        source_filename: str,
    ) -> InvestmentHolding:
        cursor = self._connection.execute(
            """INSERT OR REPLACE INTO investment_holdings(
                   account_id, valuation_date, asset_class, fund_code, fund_name,
                   units, unit_price, market_value, market_value_cents,
                   allocation_pct, source_filename
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                valuation_date,
                asset_class,
                fund_code,
                fund_name,
                units,
                unit_price,
                market_value,
                to_cents(market_value),
                allocation_pct,
                source_filename,
            ),
        )
        holding = self.get(cursor.lastrowid)
        if holding is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Stored investment holding could not be retrieved")
        return holding

    def latest(
        self, account_id: int | None = None, account_type: str | None = None
    ) -> list[dict[str, object]]:
        """Most recent valuation of each fund, with its account."""
        filters = []
        params: list[object] = []
        if account_id is not None:
            filters.append("latest.account_id = ?")
            params.append(account_id)
        if account_type is not None:
            filters.append("a.account_type = ?")
            params.append(account_type)
        where = f"WHERE {' AND '.join(filters)} AND" if filters else "WHERE"
        sql_template = """
            WITH latest AS (
                SELECT h.*, ROW_NUMBER() OVER (
                    PARTITION BY h.account_id, h.fund_code
                    ORDER BY h.valuation_date DESC, h.id DESC
                ) AS row_number
                FROM investment_holdings h
            )
            SELECT latest.*, a.name AS account_name, a.account_number, a.institution
            FROM latest JOIN accounts a ON a.id = latest.account_id
            __LATEST_FILTER__
            ORDER BY a.name, latest.market_value_cents DESC
            """
        query = sql_template.replace("__LATEST_FILTER__", f"{where} latest.row_number = 1")
        rows = self._connection.execute(query, params).fetchall()
        results = [dict(row) for row in rows]
        for result in results:
            result["market_value"] = float(from_cents(result["market_value_cents"]))
        return results

    def get(self, holding_id: int | None) -> InvestmentHolding | None:
        if holding_id is None:
            return None
        row = self._connection.execute(
            f"{self._SELECT} WHERE id = ?",  # noqa: S608 - static query fragment
            (holding_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_account(self, account_id: int) -> list[InvestmentHolding]:
        rows = self._connection.execute(
            f"{self._SELECT} WHERE account_id = ? ORDER BY valuation_date, id",  # noqa: S608
            (account_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def delete_for_account_date(self, account_id: int, valuation_date: str) -> None:
        self._connection.execute(
            "DELETE FROM investment_holdings WHERE account_id = ? AND valuation_date = ?",
            (account_id, valuation_date),
        )

    def delete_for_account_source_prefix(self, account_id: int, source_prefix: str) -> None:
        self._connection.execute(
            "DELETE FROM investment_holdings WHERE account_id = ? AND source_filename LIKE ?",
            (account_id, f"{source_prefix}%"),
        )

    _SELECT = """SELECT id, account_id, valuation_date, asset_class, fund_code, fund_name,
                         units, unit_price, market_value_cents, allocation_pct, source_filename
                  FROM investment_holdings"""

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> InvestmentHolding:
        holding_id = InvestmentHoldingRepository._required_int(row[0])
        account_id = InvestmentHoldingRepository._required_int(row[1])
        return InvestmentHolding(
            id=holding_id,
            account_id=account_id,
            valuation_date=str(row[2]),
            asset_class=str(row[3]) if row[3] is not None else None,
            fund_code=str(row[4]),
            fund_name=str(row[5]),
            units=InvestmentHoldingRepository._required_float(row[6]),
            unit_price=InvestmentHoldingRepository._required_float(row[7]),
            market_value=float(from_cents(row[8])),
            allocation_pct=InvestmentHoldingRepository._optional_float(row[9]),
            source_filename=str(row[10]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Investment holding id must be an integer")
        return value

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("Investment holding numeric value has an invalid type")
        return float(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        return InvestmentHoldingRepository._required_float(value)
