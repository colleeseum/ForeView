from __future__ import annotations

import sqlite3


class EmploymentIncomeRecordsMigration:
    """Add the manually identified bonus to annual employment facts."""

    version = 6
    name = "employment_income_records"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """ALTER TABLE annual_employment_actuals
               ADD COLUMN bonus_cents INTEGER NOT NULL DEFAULT 0
               CHECK (bonus_cents >= 0)"""
        )
