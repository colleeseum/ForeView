from __future__ import annotations

import sqlite3


class CorrectionRevisionHistoryMigration:
    """Replace mutable corrections with an append-only revision history."""

    version = 13
    name = "correction_revision_history"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute("ALTER TABLE corrections RENAME TO corrections_v12")
        connection.execute(
            """CREATE TABLE corrections (
                   id INTEGER PRIMARY KEY,
                   person_id INTEGER NOT NULL REFERENCES people(id),
                   tax_year INTEGER NOT NULL CHECK(tax_year BETWEEN 1900 AND 2200),
                   concept TEXT NOT NULL CHECK(length(trim(concept)) > 0),
                   revision_number INTEGER NOT NULL CHECK(revision_number > 0),
                   revision_kind TEXT NOT NULL CHECK(
                       revision_kind IN ('create', 'edit', 'confirm', 'remove')
                   ),
                   correct_amount_cents INTEGER CHECK(
                       correct_amount_cents IS NULL OR correct_amount_cents >= 0
                   ),
                   reason TEXT NOT NULL CHECK(length(trim(reason)) > 0),
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
                   source_at_correction_source_version TEXT,
                   source_at_correction_document_hash TEXT,
                   fingerprint TEXT NOT NULL,
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   UNIQUE(person_id, tax_year, concept, revision_number)
               )"""
        )
        connection.execute(
            """INSERT INTO corrections(
                   person_id, tax_year, concept, revision_number, revision_kind,
                   correct_amount_cents, reason, source_at_correction_id,
                   source_at_correction_document_kind, source_at_correction_jurisdiction,
                   source_at_correction_concept, source_at_correction_description,
                   source_at_correction_reported_amount_cents,
                   source_at_correction_determined_amount_cents,
                   source_at_correction_line_code, source_at_correction_source,
                   source_at_correction_source_version, source_at_correction_document_hash,
                   fingerprint, created_at
               )
               SELECT person_id, tax_year, concept, 1, 'create',
                      correct_amount_cents, reason, source_at_correction_id,
                      source_at_correction_document_kind,
                      source_at_correction_jurisdiction,
                      source_at_correction_concept,
                      source_at_correction_description,
                      source_at_correction_reported_amount_cents,
                      source_at_correction_determined_amount_cents,
                      source_at_correction_line_code,
                      source_at_correction_source,
                      NULLIF(source_at_correction_source_version, ''),
                      NULLIF(source_at_correction_document_hash, ''),
                      fingerprint, created_at
                 FROM corrections_v12"""
        )
        connection.execute(
            """INSERT INTO corrections(
                   person_id, tax_year, concept, revision_number, revision_kind,
                   correct_amount_cents, reason, source_at_correction_id,
                   source_at_correction_document_kind, source_at_correction_jurisdiction,
                   source_at_correction_concept, source_at_correction_description,
                   source_at_correction_reported_amount_cents,
                   source_at_correction_determined_amount_cents,
                   source_at_correction_line_code, source_at_correction_source,
                   source_at_correction_source_version, source_at_correction_document_hash,
                   fingerprint, created_at
               )
               SELECT person_id, tax_year, concept, 2, 'remove',
                      correct_amount_cents, reason, source_at_correction_id,
                      source_at_correction_document_kind,
                      source_at_correction_jurisdiction,
                      source_at_correction_concept,
                      source_at_correction_description,
                      source_at_correction_reported_amount_cents,
                      source_at_correction_determined_amount_cents,
                      source_at_correction_line_code,
                      source_at_correction_source,
                      NULLIF(source_at_correction_source_version, ''),
                      NULLIF(source_at_correction_document_hash, ''),
                      fingerprint, COALESCE(deleted_at, updated_at, created_at)
                 FROM corrections_v12
                WHERE deleted_at IS NOT NULL"""
        )
        connection.execute("DROP TABLE corrections_v12")
        connection.execute(
            """CREATE INDEX corrections_person_year
                   ON corrections(person_id, tax_year)"""
        )
        connection.execute(
            """CREATE INDEX corrections_stream_revision
                   ON corrections(person_id, tax_year, concept, revision_number DESC)"""
        )
