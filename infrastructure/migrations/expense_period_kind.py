# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3


class ExpensePeriodKindMigration:
    """Distinguish annual or one-time amounts from recurring statement periods."""

    version = 17
    name = "expense_period_kind"

    def apply(self, connection: sqlite3.Connection) -> None:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(expense_records)")}
        if "period_kind" not in columns:
            connection.execute(
                """ALTER TABLE expense_records
                       ADD COLUMN period_kind TEXT NOT NULL DEFAULT 'annual_or_one_time'
                       CHECK(period_kind IN ('annual_or_one_time', 'recurring_statement'))"""
            )
