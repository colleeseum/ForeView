from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from domain.employment_projection_settings import EmploymentProjectionSettings
from domain.money import MoneyInput, from_cents, to_cents
from domain.rates import from_rate_micros, to_rate_micros


class EmploymentProjectionSettingsRepository:
    """Persist recurring employment assumptions for a scenario and person."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        scenario_id: int,
        person_id: int,
        *,
        default_raise: Decimal | str | int | float = 0,
        retirement_date: str | None = None,
        recurring_rrsp_contribution: MoneyInput = 0,
        recurring_rrsp_deduction: MoneyInput = 0,
        recurring_other_income: MoneyInput = 0,
    ) -> EmploymentProjectionSettings:
        if retirement_date is not None:
            date.fromisoformat(retirement_date)
        rate_micros = to_rate_micros(default_raise)
        if rate_micros < -1_000_000:
            raise ValueError("Default raise cannot reduce salary below zero")
        amounts = tuple(
            to_cents(value)
            for value in (
                recurring_rrsp_contribution,
                recurring_rrsp_deduction,
                recurring_other_income,
            )
        )
        if any(value < 0 for value in amounts):
            raise ValueError("Recurring employment values cannot be negative")
        self._connection.execute(
            """INSERT INTO employment_projection_settings(
                   scenario_id, person_id, default_raise_micros, retirement_date,
                   recurring_rrsp_contribution_cents, recurring_rrsp_deduction_cents,
                   recurring_other_income_cents
               ) VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(scenario_id, person_id) DO UPDATE SET
                   default_raise_micros = excluded.default_raise_micros,
                   retirement_date = excluded.retirement_date,
                   recurring_rrsp_contribution_cents = excluded.recurring_rrsp_contribution_cents,
                   recurring_rrsp_deduction_cents = excluded.recurring_rrsp_deduction_cents,
                   recurring_other_income_cents = excluded.recurring_other_income_cents""",
            (scenario_id, person_id, rate_micros, retirement_date, *amounts),
        )
        result = self.get(scenario_id, person_id)
        if result is None:  # pragma: no cover
            raise RuntimeError("Employment projection settings could not be retrieved")
        return result

    def get(self, scenario_id: int, person_id: int) -> EmploymentProjectionSettings | None:
        row = self._connection.execute(
            """SELECT scenario_id, person_id, default_raise_micros, retirement_date,
                      recurring_rrsp_contribution_cents, recurring_rrsp_deduction_cents,
                      recurring_other_income_cents
                 FROM employment_projection_settings
                WHERE scenario_id = ? AND person_id = ?""",
            (scenario_id, person_id),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_scenario(self, scenario_id: int) -> list[EmploymentProjectionSettings]:
        rows = self._connection.execute(
            """SELECT scenario_id, person_id, default_raise_micros, retirement_date,
                      recurring_rrsp_contribution_cents, recurring_rrsp_deduction_cents,
                      recurring_other_income_cents
                 FROM employment_projection_settings WHERE scenario_id = ? ORDER BY person_id""",
            (scenario_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> EmploymentProjectionSettings:
        return EmploymentProjectionSettings(
            scenario_id=EmploymentProjectionSettingsRepository._required_int(row[0]),
            person_id=EmploymentProjectionSettingsRepository._required_int(row[1]),
            default_raise=from_rate_micros(row[2]),
            retirement_date=str(row[3]) if row[3] is not None else None,
            recurring_rrsp_contribution=from_cents(row[4]),
            recurring_rrsp_deduction=from_cents(row[5]),
            recurring_other_income=from_cents(row[6]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Employment projection identifier must be an integer")
        return value
