# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from decimal import Decimal

from domain.household_expense_plan import HouseholdExpensePlan
from domain.money import MoneyInput, from_cents, to_cents
from domain.rates import from_rate_micros, to_rate_micros


class HouseholdExpensePlanRepository:
    """Persist one household spending plan per scenario."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        scenario_id: int,
        *,
        start_year: int,
        required_annual_amount: MoneyInput,
        required_annual_growth: Decimal | str | int | float = 0,
        discretionary_annual_amount: MoneyInput = 0,
        discretionary_annual_growth: Decimal | str | int | float = 0,
    ) -> HouseholdExpensePlan:
        if start_year < 1900:
            raise ValueError("Expense start year must be at least 1900")
        amounts = tuple(
            to_cents(value) for value in (required_annual_amount, discretionary_annual_amount)
        )
        growth = tuple(
            to_rate_micros(value) for value in (required_annual_growth, discretionary_annual_growth)
        )
        if any(value < 0 for value in amounts):
            raise ValueError("Annual household expenses cannot be negative")
        if any(value < -1_000_000 for value in growth):
            raise ValueError("Expense growth cannot reduce spending below zero")
        self._connection.execute(
            """INSERT INTO household_expense_plans(
                   scenario_id, start_year, required_annual_amount_cents,
                   required_annual_growth_micros, discretionary_annual_amount_cents,
                   discretionary_annual_growth_micros
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(scenario_id) DO UPDATE SET
                   start_year = excluded.start_year,
                   required_annual_amount_cents = excluded.required_annual_amount_cents,
                   required_annual_growth_micros = excluded.required_annual_growth_micros,
                   discretionary_annual_amount_cents = excluded.discretionary_annual_amount_cents,
                   discretionary_annual_growth_micros = excluded.discretionary_annual_growth_micros""",
            (scenario_id, start_year, *amounts[:1], growth[0], amounts[1], growth[1]),
        )
        result = self.get(scenario_id)
        if result is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Household expense plan could not be retrieved")
        return result

    def get(self, scenario_id: int | None) -> HouseholdExpensePlan | None:
        if scenario_id is None:
            return None
        row = self._connection.execute(
            """SELECT scenario_id, start_year, required_annual_amount_cents,
                      required_annual_growth_micros, discretionary_annual_amount_cents,
                      discretionary_annual_growth_micros
                 FROM household_expense_plans WHERE scenario_id = ?""",
            (scenario_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> HouseholdExpensePlan:
        if not isinstance(row[0], int) or not isinstance(row[1], int):
            raise TypeError("Household expense identifiers must be integers")
        return HouseholdExpensePlan(
            scenario_id=row[0],
            start_year=row[1],
            required_annual_amount=from_cents(row[2]),
            required_annual_growth=from_rate_micros(row[3]),
            discretionary_annual_amount=from_cents(row[4]),
            discretionary_annual_growth=from_rate_micros(row[5]),
        )
