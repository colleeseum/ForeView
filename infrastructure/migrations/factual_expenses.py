# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3


def create_expense_records_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE expense_records (
               id INTEGER PRIMARY KEY,
               name TEXT NOT NULL CHECK(length(trim(name)) > 0),
               category_id INTEGER NOT NULL REFERENCES expense_categories(id),
               category_name TEXT NOT NULL,
               classification TEXT NOT NULL CHECK(classification IN ('required', 'discretionary')),
               amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
               period_start TEXT NOT NULL,
               period_end TEXT NOT NULL,
               source_kind TEXT NOT NULL CHECK(source_kind IN ('manual', 'imported')),
               source_document_id INTEGER REFERENCES import_batches(id),
               source_name TEXT,
               parser_name TEXT,
               parser_version TEXT,
               source_hash TEXT,
               association_kind TEXT NOT NULL DEFAULT 'household' CHECK(
                   association_kind IN ('household', 'person', 'account', 'real_estate')
               ),
               association_id INTEGER,
               overlap_status TEXT NOT NULL DEFAULT 'clear' CHECK(
                   overlap_status IN ('clear', 'potential', 'resolved_include', 'resolved_exclude')
               ),
               overlap_resolution_note TEXT,
               created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
               updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
               CHECK(period_end >= period_start),
               CHECK(
                   (source_kind = 'manual' AND source_document_id IS NULL
                    AND source_name IS NULL AND parser_name IS NULL AND parser_version IS NULL
                    AND source_hash IS NULL) OR
                   (source_kind = 'imported' AND source_document_id IS NOT NULL
                    AND length(trim(source_name)) > 0 AND length(trim(parser_name)) > 0
                    AND length(trim(source_hash)) > 0)
               ),
               CHECK(
                   (association_kind = 'household' AND association_id IS NULL) OR
                   (association_kind <> 'household' AND association_id IS NOT NULL)
               )
           )"""
    )


def create_expense_record_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE INDEX expense_records_category_period
               ON expense_records(category_id, period_start, period_end)"""
    )
    connection.execute(
        """CREATE INDEX expense_records_association
               ON expense_records(association_kind, association_id)"""
    )
    connection.execute(
        """CREATE INDEX expense_records_source_hash
               ON expense_records(source_hash)"""
    )


class FactualExpensesMigration:
    """Add user-defined factual expense categories and auditable expense records."""

    version = 14
    name = "factual_expenses"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE expense_categories (
                   id INTEGER PRIMARY KEY,
                   name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(name)) > 0),
                   classification TEXT NOT NULL CHECK(classification IN ('required', 'discretionary')),
                   is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        create_expense_records_table(connection)
        create_expense_record_indexes(connection)
