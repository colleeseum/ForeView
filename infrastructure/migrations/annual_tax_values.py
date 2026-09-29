from __future__ import annotations

import sqlite3


class AnnualTaxValuesMigration:
    """Store extensible facts from tax returns and assessment notices."""

    version = 11
    name = "annual_tax_values"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE annual_tax_values (
                id INTEGER PRIMARY KEY,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                tax_year INTEGER NOT NULL CHECK (tax_year >= 1900),
                effective_year INTEGER NOT NULL CHECK (effective_year >= 1900),
                document_kind TEXT NOT NULL CHECK (document_kind IN ('return', 'assessment')),
                jurisdiction TEXT NOT NULL,
                concept TEXT NOT NULL,
                description TEXT NOT NULL,
                reported_amount_cents INTEGER,
                determined_amount_cents INTEGER,
                line_code TEXT,
                source TEXT NOT NULL,
                source_version TEXT NOT NULL,
                document_hash TEXT NOT NULL,
                CHECK (reported_amount_cents IS NOT NULL OR determined_amount_cents IS NOT NULL),
                UNIQUE(
                    person_id, tax_year, document_kind, jurisdiction,
                    concept, effective_year
                )
            );

            CREATE INDEX annual_tax_values_person_year
                ON annual_tax_values(person_id, tax_year DESC);
            """
        )
