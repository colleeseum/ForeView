# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3


class FactualExpensesMigration:
    """Add user-defined factual expense categories and expense records."""

    version = 14
    name = "factual_expenses"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE expense_categories (
                   id INTEGER PRIMARY KEY,
                   name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(name)) > 0),
                   classification TEXT NOT NULL CHECK(
                       classification IN ('required', 'discretionary')
                   ),
                   is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        connection.execute(
            """CREATE TABLE expense_records (
                   id INTEGER PRIMARY KEY,
                   name TEXT NOT NULL CHECK(length(trim(name)) > 0),
                   category_id INTEGER NOT NULL REFERENCES expense_categories(id),
                   amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
                   period_start TEXT NOT NULL,
                   period_end TEXT NOT NULL,
                   source_kind TEXT NOT NULL CHECK(source_kind IN ('manual', 'imported')),
                   source_document_id INTEGER,
                   association_kind TEXT NOT NULL DEFAULT 'household' CHECK(
                       association_kind IN ('household', 'person', 'asset')
                   ),
                   association_id INTEGER,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   CHECK(period_end >= period_start),
                   CHECK(
                       (source_kind = 'manual' AND source_document_id IS NULL) OR
                       (source_kind = 'imported' AND source_document_id IS NOT NULL)
                   ),
                   CHECK(
                       (association_kind = 'household' AND association_id IS NULL) OR
                       (association_kind IN ('person', 'asset') AND association_id IS NOT NULL)
                   )
               )"""
        )
        connection.execute(
            """CREATE INDEX expense_records_category_period
                   ON expense_records(category_id, period_start, period_end)"""
        )
        connection.execute(
            """CREATE INDEX expense_records_association
                   ON expense_records(association_kind, association_id)"""
        )
