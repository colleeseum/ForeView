# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from infrastructure.migrations.factual_expenses import (
    create_expense_record_indexes,
    create_expense_records_table,
)


class FactualExpenseSchemaUpgradeMigration:
    """Upgrade draft migration 14 databases to the reviewed expense schema."""

    version = 15
    name = "factual_expense_schema_upgrade"

    def apply(self, connection: sqlite3.Connection) -> None:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'expense_records'"
        ).fetchone()
        if table_sql is None:
            raise RuntimeError("Migration 14 must create expense_records before migration 15")
        foreign_keys = connection.execute("PRAGMA foreign_key_list(expense_records)").fetchall()
        has_import_batch_reference = any(str(row[2]) == "import_batches" for row in foreign_keys)
        if "'account'" in str(table_sql[0]) and has_import_batch_reference:
            return

        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(expense_records)")}
        if connection.execute(
            "SELECT 1 FROM expense_records WHERE association_kind = 'asset' LIMIT 1"
        ).fetchone():
            raise RuntimeError(
                "Legacy asset expense associations require manual account/real-estate classification"
            )
        connection.execute("ALTER TABLE expense_records RENAME TO expense_records_v14")
        create_expense_records_table(connection)
        if "category_name" in columns:
            connection.execute(
                """INSERT INTO expense_records(
                       id, name, category_id, category_name, classification, amount_cents,
                       period_start, period_end, source_kind, source_document_id, source_name,
                       parser_name, parser_version, source_hash, association_kind, association_id,
                       overlap_status, overlap_resolution_note, created_at, updated_at
                   )
                   SELECT id, name, category_id, category_name, classification, amount_cents,
                          period_start, period_end, source_kind, source_document_id, source_name,
                          parser_name, parser_version, source_hash, association_kind, association_id,
                          overlap_status, overlap_resolution_note, created_at, updated_at
                     FROM expense_records_v14"""
            )
        else:
            connection.execute(
                """INSERT INTO expense_records(
                       id, name, category_id, category_name, classification, amount_cents,
                       period_start, period_end, source_kind, source_document_id,
                       association_kind, association_id, created_at, updated_at
                   )
                   SELECT e.id, e.name, e.category_id, c.name, c.classification, e.amount_cents,
                          e.period_start, e.period_end, e.source_kind, e.source_document_id,
                          e.association_kind, e.association_id, e.created_at, e.created_at
                     FROM expense_records_v14 e
                     JOIN expense_categories c ON c.id = e.category_id"""
            )
        connection.execute("DROP TABLE expense_records_v14")
        create_expense_record_indexes(connection)
