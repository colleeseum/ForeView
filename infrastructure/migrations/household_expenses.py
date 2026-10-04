from __future__ import annotations

import sqlite3


class HouseholdExpensesMigration:
    """Add scenario-level required and discretionary spending assumptions."""

    version = 9
    name = "household_expenses"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE household_expense_plans (
                   scenario_id INTEGER PRIMARY KEY REFERENCES scenarios(id) ON DELETE CASCADE,
                   start_year INTEGER NOT NULL CHECK(start_year >= 1900),
                   required_annual_amount_cents INTEGER NOT NULL CHECK(required_annual_amount_cents >= 0),
                   required_annual_growth_micros INTEGER NOT NULL CHECK(required_annual_growth_micros >= -1000000),
                   discretionary_annual_amount_cents INTEGER NOT NULL CHECK(discretionary_annual_amount_cents >= 0),
                   discretionary_annual_growth_micros INTEGER NOT NULL CHECK(discretionary_annual_growth_micros >= -1000000)
               )"""
        )
