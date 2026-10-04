from __future__ import annotations

import sqlite3


class CorrectionsTableMigration:
    """Add corrections table for factual income and tax value corrections."""

    version = 12
    name = "corrections_table"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE corrections (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   person_id INTEGER NOT NULL REFERENCES people(id),
                   tax_year INTEGER NOT NULL CHECK(tax_year >= 1900 AND tax_year <= 2200),
                   concept TEXT NOT NULL,
                   correct_amount_cents INTEGER,
                   reason TEXT NOT NULL CHECK(length(reason) > 0),
                   source_at_correction_id INTEGER,
                   source_at_correction_document_kind TEXT,
                   source_at_correction_jurisdiction TEXT,
                   source_at_correction_concept TEXT,
                   source_at_correction_description TEXT,
                   source_at_correction_reported_amount_cents INTEGER CHECK(
                       source_at_correction_reported_amount_cents IS NULL OR
                       source_at_correction_reported_amount_cents >= 0
                   ),
                   source_at_correction_determined_amount_cents INTEGER CHECK(
                       source_at_correction_determined_amount_cents IS NULL OR
                       source_at_correction_determined_amount_cents >= 0
                   ),
                   source_at_correction_line_code TEXT,
                   source_at_correction_source TEXT NOT NULL,
                   source_at_correction_source_version TEXT NOT NULL,
                   source_at_correction_document_hash TEXT NOT NULL,
                   fingerprint TEXT NOT NULL,
                   review_required BOOLEAN NOT NULL DEFAULT 0,
                   revision_number INTEGER NOT NULL DEFAULT 1 CHECK(revision_number >= 1),
                   expected_revision_guard INTEGER NOT NULL DEFAULT 0,
                   created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   deleted_at DATETIME,
                   CHECK(correct_amount_cents IS NULL OR correct_amount_cents >= 0),
                   UNIQUE(person_id, tax_year, concept)
               )"""
        )
        connection.execute(
            "CREATE INDEX idx_corrections_person_year ON corrections(person_id, tax_year)"
        )
        connection.execute("CREATE INDEX idx_corrections_concept ON corrections(concept)")
        connection.execute("CREATE INDEX idx_corrections_deleted ON corrections(deleted_at)")
