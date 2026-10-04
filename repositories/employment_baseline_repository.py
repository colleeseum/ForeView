# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from datetime import date

from domain.employment_baseline import EmploymentBaseline
from domain.money import MoneyInput, from_cents, to_cents


class EmploymentBaselineRepository:
    """Persist factual salary baselines without projection behavior."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        person_id: int,
        effective_date: str,
        annual_salary: MoneyInput,
        province_of_employment: str,
        payroll_plan: str,
        source: str | None = None,
    ) -> EmploymentBaseline:
        date.fromisoformat(effective_date)
        province = province_of_employment.strip().upper()
        plan = payroll_plan.strip().upper()
        if not province:
            raise ValueError("Province of employment is required")
        if plan not in {"CPP", "QPP"}:
            raise ValueError("Payroll plan must be CPP or QPP")
        salary_cents = to_cents(annual_salary)
        if salary_cents < 0:
            raise ValueError("Annual salary cannot be negative")
        self._connection.execute(
            """INSERT INTO employment_baselines(
                   person_id, effective_date, annual_salary_cents,
                   province_of_employment, payroll_plan, source
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(person_id, effective_date) DO UPDATE SET
                   annual_salary_cents = excluded.annual_salary_cents,
                   province_of_employment = excluded.province_of_employment,
                   payroll_plan = excluded.payroll_plan,
                   source = excluded.source""",
            (person_id, effective_date, salary_cents, province, plan, source or None),
        )
        result = self.get_effective(person_id, effective_date)
        if result is None:  # pragma: no cover - SQLite upsert/select invariant
            raise RuntimeError("Employment baseline could not be retrieved")
        return result

    def get_effective(self, person_id: int, on_date: str) -> EmploymentBaseline | None:
        date.fromisoformat(on_date)
        row = self._connection.execute(
            """SELECT id, person_id, effective_date, annual_salary_cents,
                      province_of_employment, payroll_plan, source
                 FROM employment_baselines
                WHERE person_id = ? AND effective_date <= ?
                ORDER BY effective_date DESC, id DESC LIMIT 1""",
            (person_id, on_date),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_person(self, person_id: int) -> list[EmploymentBaseline]:
        rows = self._connection.execute(
            """SELECT id, person_id, effective_date, annual_salary_cents,
                      province_of_employment, payroll_plan, source
                 FROM employment_baselines WHERE person_id = ?
                ORDER BY effective_date, id""",
            (person_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> EmploymentBaseline:
        return EmploymentBaseline(
            id=EmploymentBaselineRepository._required_int(row[0]),
            person_id=EmploymentBaselineRepository._required_int(row[1]),
            effective_date=str(row[2]),
            annual_salary=from_cents(row[3]),
            province_of_employment=str(row[4]),
            payroll_plan=str(row[5]),
            source=str(row[6]) if row[6] is not None else None,
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Employment baseline identifier must be an integer")
        return value
