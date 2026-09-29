from __future__ import annotations

import sqlite3
from decimal import Decimal

from domain.employment_projection_override import EmploymentProjectionOverride
from domain.money import MoneyInput, from_cents, to_cents
from domain.rates import from_rate_micros, to_rate_micros


class EmploymentProjectionOverrideRepository:
    """Persist sparse annual replacements for employment projections."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        scenario_id: int,
        person_id: int,
        projection_year: int,
        *,
        salary: MoneyInput | None = None,
        raise_rate: Decimal | str | int | float | None = None,
        rrsp_contribution: MoneyInput | None = None,
        rrsp_deduction: MoneyInput | None = None,
        other_income: MoneyInput | None = None,
    ) -> EmploymentProjectionOverride:
        if projection_year < 1900:
            raise ValueError("Projection year must be 1900 or later")
        amounts = tuple(
            None if value is None else to_cents(value)
            for value in (salary, rrsp_contribution, rrsp_deduction, other_income)
        )
        if any(value is not None and value < 0 for value in amounts):
            raise ValueError("Employment overrides cannot be negative")
        rate_micros = None if raise_rate is None else to_rate_micros(raise_rate)
        if rate_micros is not None and rate_micros < -1_000_000:
            raise ValueError("Raise override cannot reduce salary below zero")
        self._connection.execute(
            """INSERT INTO employment_projection_overrides(
                   scenario_id, person_id, projection_year, salary_cents, raise_micros,
                   rrsp_contribution_cents, rrsp_deduction_cents, other_income_cents
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(scenario_id, person_id, projection_year) DO UPDATE SET
                   salary_cents = excluded.salary_cents,
                   raise_micros = excluded.raise_micros,
                   rrsp_contribution_cents = excluded.rrsp_contribution_cents,
                   rrsp_deduction_cents = excluded.rrsp_deduction_cents,
                   other_income_cents = excluded.other_income_cents""",
            (
                scenario_id,
                person_id,
                projection_year,
                amounts[0],
                rate_micros,
                amounts[1],
                amounts[2],
                amounts[3],
            ),
        )
        result = self.get(scenario_id, person_id, projection_year)
        if result is None:  # pragma: no cover
            raise RuntimeError("Employment projection override could not be retrieved")
        return result

    def get(
        self, scenario_id: int, person_id: int, projection_year: int
    ) -> EmploymentProjectionOverride | None:
        row = self._connection.execute(
            """SELECT scenario_id, person_id, projection_year, salary_cents, raise_micros,
                      rrsp_contribution_cents, rrsp_deduction_cents, other_income_cents
                 FROM employment_projection_overrides
                WHERE scenario_id = ? AND person_id = ? AND projection_year = ?""",
            (scenario_id, person_id, projection_year),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_person(
        self, scenario_id: int, person_id: int
    ) -> list[EmploymentProjectionOverride]:
        rows = self._connection.execute(
            """SELECT scenario_id, person_id, projection_year, salary_cents, raise_micros,
                      rrsp_contribution_cents, rrsp_deduction_cents, other_income_cents
                 FROM employment_projection_overrides
                WHERE scenario_id = ? AND person_id = ? ORDER BY projection_year""",
            (scenario_id, person_id),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, scenario_id: int, person_id: int, projection_year: int) -> None:
        self._connection.execute(
            """DELETE FROM employment_projection_overrides
                WHERE scenario_id = ? AND person_id = ? AND projection_year = ?""",
            (scenario_id, person_id, projection_year),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> EmploymentProjectionOverride:
        return EmploymentProjectionOverride(
            scenario_id=EmploymentProjectionOverrideRepository._required_int(row[0]),
            person_id=EmploymentProjectionOverrideRepository._required_int(row[1]),
            projection_year=EmploymentProjectionOverrideRepository._required_int(row[2]),
            salary=None if row[3] is None else from_cents(row[3]),
            raise_rate=None if row[4] is None else from_rate_micros(row[4]),
            rrsp_contribution=None if row[5] is None else from_cents(row[5]),
            rrsp_deduction=None if row[6] is None else from_cents(row[6]),
            other_income=None if row[7] is None else from_cents(row[7]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Employment projection identifier must be an integer")
        return value
