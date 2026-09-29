from __future__ import annotations

import sqlite3


class EmploymentProjectionMigration:
    """Add typed factual and scenario inputs for employment projections."""

    version = 5
    name = "employment_projection"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE employment_baselines (
                id INTEGER PRIMARY KEY,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                effective_date TEXT NOT NULL,
                annual_salary_cents INTEGER NOT NULL CHECK (annual_salary_cents >= 0),
                province_of_employment TEXT NOT NULL,
                payroll_plan TEXT NOT NULL CHECK (payroll_plan IN ('CPP', 'QPP')),
                source TEXT,
                UNIQUE(person_id, effective_date)
            );

            CREATE TABLE annual_employment_actuals (
                id INTEGER PRIMARY KEY,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                tax_year INTEGER NOT NULL CHECK (tax_year >= 1900),
                salary_income_cents INTEGER NOT NULL CHECK (salary_income_cents >= 0),
                other_income_cents INTEGER NOT NULL DEFAULT 0,
                rrsp_contribution_cents INTEGER NOT NULL DEFAULT 0,
                rrsp_deduction_cents INTEGER NOT NULL DEFAULT 0,
                cpp_qpp_cents INTEGER NOT NULL DEFAULT 0,
                ei_cents INTEGER NOT NULL DEFAULT 0,
                qpip_cents INTEGER NOT NULL DEFAULT 0,
                federal_tax_cents INTEGER NOT NULL DEFAULT 0,
                provincial_tax_cents INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                UNIQUE(person_id, tax_year)
            );

            CREATE TABLE employment_projection_settings (
                scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                default_raise_micros INTEGER NOT NULL DEFAULT 0,
                retirement_date TEXT,
                recurring_rrsp_contribution_cents INTEGER NOT NULL DEFAULT 0,
                recurring_rrsp_deduction_cents INTEGER NOT NULL DEFAULT 0,
                recurring_other_income_cents INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(scenario_id, person_id)
            );

            CREATE TABLE employment_projection_overrides (
                scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                projection_year INTEGER NOT NULL CHECK (projection_year >= 1900),
                salary_cents INTEGER,
                raise_micros INTEGER,
                rrsp_contribution_cents INTEGER,
                rrsp_deduction_cents INTEGER,
                other_income_cents INTEGER,
                PRIMARY KEY(scenario_id, person_id, projection_year)
            );
            """
        )
