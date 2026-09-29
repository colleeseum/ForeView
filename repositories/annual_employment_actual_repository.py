from __future__ import annotations

import sqlite3

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.money import MoneyInput, from_cents, to_cents


class AnnualEmploymentActualRepository:
    """Persist historical annual employment facts."""

    _MONEY_FIELDS = (
        "salary_income",
        "other_income",
        "rrsp_contribution",
        "rrsp_deduction",
        "cpp_qpp",
        "ei",
        "qpip",
        "federal_tax",
        "provincial_tax",
    )

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        person_id: int,
        tax_year: int,
        salary_income: MoneyInput,
        *,
        bonus: MoneyInput = 0,
        other_income: MoneyInput = 0,
        rrsp_contribution: MoneyInput = 0,
        rrsp_deduction: MoneyInput = 0,
        cpp_qpp: MoneyInput = 0,
        ei: MoneyInput = 0,
        qpip: MoneyInput = 0,
        federal_tax: MoneyInput = 0,
        provincial_tax: MoneyInput = 0,
        source: str | None = None,
    ) -> AnnualEmploymentActual:
        if tax_year < 1900:
            raise ValueError("Tax year must be 1900 or later")
        values = tuple(
            to_cents(value)
            for value in (
                salary_income,
                bonus,
                other_income,
                rrsp_contribution,
                rrsp_deduction,
                cpp_qpp,
                ei,
                qpip,
                federal_tax,
                provincial_tax,
            )
        )
        if any(value < 0 for value in values):
            raise ValueError("Annual employment facts cannot be negative")
        if values[1] > values[0]:
            raise ValueError("Bonus cannot exceed employment income")
        self._connection.execute(
            """INSERT INTO annual_employment_actuals(
                   person_id, tax_year, salary_income_cents, bonus_cents, other_income_cents,
                   rrsp_contribution_cents, rrsp_deduction_cents, cpp_qpp_cents,
                   ei_cents, qpip_cents, federal_tax_cents, provincial_tax_cents, source
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(person_id, tax_year) DO UPDATE SET
                   salary_income_cents = excluded.salary_income_cents,
                   bonus_cents = excluded.bonus_cents,
                   other_income_cents = excluded.other_income_cents,
                   rrsp_contribution_cents = excluded.rrsp_contribution_cents,
                   rrsp_deduction_cents = excluded.rrsp_deduction_cents,
                   cpp_qpp_cents = excluded.cpp_qpp_cents,
                   ei_cents = excluded.ei_cents,
                   qpip_cents = excluded.qpip_cents,
                   federal_tax_cents = excluded.federal_tax_cents,
                   provincial_tax_cents = excluded.provincial_tax_cents,
                   source = excluded.source""",
            (person_id, tax_year, *values, source or None),
        )
        result = self.get(person_id, tax_year)
        if result is None:  # pragma: no cover
            raise RuntimeError("Annual employment actual could not be retrieved")
        return result

    def get(self, person_id: int, tax_year: int) -> AnnualEmploymentActual | None:
        row = self._connection.execute(
            """SELECT id, person_id, tax_year, salary_income_cents, other_income_cents,
                      rrsp_contribution_cents, rrsp_deduction_cents, cpp_qpp_cents,
                      ei_cents, qpip_cents, federal_tax_cents, provincial_tax_cents, source,
                      bonus_cents
                 FROM annual_employment_actuals
                WHERE person_id = ? AND tax_year = ?""",
            (person_id, tax_year),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_person(self, person_id: int) -> list[AnnualEmploymentActual]:
        rows = self._connection.execute(
            """SELECT id, person_id, tax_year, salary_income_cents, other_income_cents,
                      rrsp_contribution_cents, rrsp_deduction_cents, cpp_qpp_cents,
                      ei_cents, qpip_cents, federal_tax_cents, provincial_tax_cents, source,
                      bonus_cents
                 FROM annual_employment_actuals WHERE person_id = ? ORDER BY tax_year""",
            (person_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> AnnualEmploymentActual:
        amounts = [from_cents(row[index]) for index in range(3, 12)]
        return AnnualEmploymentActual(
            id=AnnualEmploymentActualRepository._required_int(row[0]),
            person_id=AnnualEmploymentActualRepository._required_int(row[1]),
            tax_year=AnnualEmploymentActualRepository._required_int(row[2]),
            salary_income=amounts[0],
            bonus=from_cents(row[13]),
            other_income=amounts[1],
            rrsp_contribution=amounts[2],
            rrsp_deduction=amounts[3],
            cpp_qpp=amounts[4],
            ei=amounts[5],
            qpip=amounts[6],
            federal_tax=amounts[7],
            provincial_tax=amounts[8],
            source=str(row[12]) if row[12] is not None else None,
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Annual employment actual identifier must be an integer")
        return value
