from __future__ import annotations

import sqlite3


class TaxAndPublicPensionRecordsMigration:
    """Add assessed-tax, registered-room, and public-pension records."""

    version = 10
    name = "tax_and_public_pension_records"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            ALTER TABLE annual_employment_actuals ADD COLUMN province_of_residence TEXT;
            ALTER TABLE annual_employment_actuals ADD COLUMN payroll_plan TEXT;

            UPDATE annual_employment_actuals
               SET province_of_residence = province_of_employment,
                   payroll_plan = CASE WHEN province_of_employment = 'QC' THEN 'QPP' ELSE 'CPP' END;

            CREATE TABLE annual_tax_assessments (
                id INTEGER PRIMARY KEY,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                tax_year INTEGER NOT NULL CHECK (tax_year >= 1900),
                jurisdiction TEXT NOT NULL,
                issued_on TEXT NOT NULL,
                total_income_cents INTEGER NOT NULL,
                net_income_cents INTEGER NOT NULL,
                taxable_income_cents INTEGER NOT NULL,
                net_tax_cents INTEGER NOT NULL,
                additional_contributions_cents INTEGER NOT NULL DEFAULT 0,
                tax_withheld_cents INTEGER NOT NULL DEFAULT 0,
                balance_cents INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL,
                source_version TEXT NOT NULL,
                document_hash TEXT NOT NULL,
                UNIQUE(person_id, tax_year, jurisdiction)
            );

            CREATE TABLE registered_plan_room_snapshots (
                id INTEGER PRIMARY KEY,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                plan_type TEXT NOT NULL,
                effective_year INTEGER NOT NULL CHECK (effective_year >= 1900),
                as_of_date TEXT NOT NULL,
                deduction_limit_cents INTEGER NOT NULL DEFAULT 0,
                unused_deduction_room_cents INTEGER NOT NULL DEFAULT 0,
                new_room_cents INTEGER NOT NULL DEFAULT 0,
                unused_contributions_cents INTEGER NOT NULL DEFAULT 0,
                available_room_cents INTEGER NOT NULL,
                source TEXT NOT NULL,
                source_version TEXT NOT NULL,
                UNIQUE(person_id, plan_type, effective_year)
            );

            CREATE TABLE public_pension_statements (
                id INTEGER PRIMARY KEY,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                issued_on TEXT NOT NULL,
                provider TEXT NOT NULL,
                excludes_second_enhancement INTEGER NOT NULL DEFAULT 0,
                source_version TEXT NOT NULL,
                document_hash TEXT NOT NULL,
                UNIQUE(person_id, provider, issued_on)
            );

            CREATE TABLE public_pension_earnings (
                statement_id INTEGER NOT NULL REFERENCES public_pension_statements(id) ON DELETE CASCADE,
                year INTEGER NOT NULL,
                qpp_earnings_cents INTEGER NOT NULL,
                cpp_earnings_cents INTEGER NOT NULL,
                status TEXT,
                PRIMARY KEY(statement_id, year)
            );

            CREATE TABLE public_pension_estimates (
                statement_id INTEGER NOT NULL REFERENCES public_pension_statements(id) ON DELETE CASCADE,
                contribution_assumption TEXT NOT NULL CHECK (contribution_assumption IN ('continue', 'stop')),
                activation_age INTEGER NOT NULL,
                monthly_amount_cents INTEGER NOT NULL,
                PRIMARY KEY(statement_id, contribution_assumption, activation_age)
            );
            """
        )
