# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3


class ExpenseIdentitiesMigration:
    """Give recurring expense evidence a stable identity for overlap detection."""

    version = 16
    name = "expense_identities"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS expense_identities (
                   id INTEGER PRIMARY KEY,
                   name TEXT NOT NULL CHECK(length(trim(name)) > 0),
                   category_id INTEGER NOT NULL REFERENCES expense_categories(id),
                   association_kind TEXT NOT NULL CHECK(
                       association_kind IN ('household', 'person', 'account', 'real_estate')
                   ),
                   association_id INTEGER,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   CHECK(
                       (association_kind = 'household' AND association_id IS NULL) OR
                       (association_kind <> 'household' AND association_id IS NOT NULL)
                   )
               )"""
        )
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS expense_identities_natural_key
                   ON expense_identities(
                       lower(trim(name)), category_id, association_kind,
                       coalesce(association_id, -1)
                   )"""
        )
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(expense_records)")}
        if "identity_id" not in columns:
            connection.execute(
                """ALTER TABLE expense_records
                       ADD COLUMN identity_id INTEGER REFERENCES expense_identities(id)"""
            )
        connection.execute(
            """INSERT OR IGNORE INTO expense_identities(
                   name, category_id, association_kind, association_id
               )
               SELECT DISTINCT trim(name), category_id, association_kind, association_id
                 FROM expense_records"""
        )
        connection.execute(
            """UPDATE expense_records AS record
                  SET identity_id = (
                      SELECT identity.id
                        FROM expense_identities AS identity
                       WHERE lower(trim(identity.name)) = lower(trim(record.name))
                         AND identity.category_id = record.category_id
                         AND identity.association_kind = record.association_kind
                         AND identity.association_id IS record.association_id
                  )
                WHERE identity_id IS NULL"""
        )
        if connection.execute(
            "SELECT 1 FROM expense_records WHERE identity_id IS NULL LIMIT 1"
        ).fetchone():
            raise RuntimeError("Every expense record must have an expense identity")
        connection.execute(
            """UPDATE expense_records AS candidate
                  SET overlap_status = 'potential', overlap_resolution_note = NULL
                WHERE candidate.overlap_status = 'clear'
                  AND EXISTS (
                      SELECT 1 FROM expense_records AS other
                       WHERE other.id <> candidate.id
                         AND other.identity_id = candidate.identity_id
                         AND other.period_start <= candidate.period_end
                         AND other.period_end >= candidate.period_start
                  )"""
        )
        connection.execute(
            """UPDATE expense_records AS candidate
                  SET overlap_status = 'clear', overlap_resolution_note = NULL
                WHERE candidate.overlap_status = 'potential'
                  AND NOT EXISTS (
                      SELECT 1 FROM expense_records AS other
                       WHERE other.id <> candidate.id
                         AND other.identity_id = candidate.identity_id
                         AND other.period_start <= candidate.period_end
                         AND other.period_end >= candidate.period_start
                  )"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS expense_records_identity_period
                   ON expense_records(identity_id, period_start, period_end)"""
        )
