from __future__ import annotations

import sqlite3


class AnnualEmploymentProvinceMigration:
    """Associate province of employment with each factual annual record."""

    version = 7
    name = "annual_employment_province"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """ALTER TABLE annual_employment_actuals
               ADD COLUMN province_of_employment TEXT"""
        )
        connection.execute(
            """UPDATE annual_employment_actuals AS actual
                  SET province_of_employment = (
                      SELECT baseline.province_of_employment
                        FROM employment_baselines AS baseline
                       WHERE baseline.person_id = actual.person_id
                         AND baseline.effective_date <= printf('%04d-12-31', actual.tax_year)
                       ORDER BY baseline.effective_date DESC, baseline.id DESC
                       LIMIT 1
                  )"""
        )
