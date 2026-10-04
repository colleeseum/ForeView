from __future__ import annotations

import sqlite3


class AnnualEmploymentProvinceBackfillMigration:
    """Backfill legacy facts when only a later employment setup exists."""

    version = 8
    name = "annual_employment_province_backfill"

    def apply(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """UPDATE annual_employment_actuals AS actual
                  SET province_of_employment = (
                      SELECT baseline.province_of_employment
                        FROM employment_baselines AS baseline
                       WHERE baseline.person_id = actual.person_id
                       ORDER BY baseline.effective_date ASC, baseline.id ASC
                       LIMIT 1
                  )
                WHERE province_of_employment IS NULL"""
        )
