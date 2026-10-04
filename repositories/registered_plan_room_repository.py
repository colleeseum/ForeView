from __future__ import annotations

import sqlite3

from domain.money import MoneyInput, from_cents, to_cents
from domain.registered_plan_room import RegisteredPlanRoom


class RegisteredPlanRoomRepository:
    """Persist official room by person rather than by financial account."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        person_id: int,
        plan_type: str,
        effective_year: int,
        as_of_date: str,
        *,
        deduction_limit: MoneyInput = 0,
        unused_deduction_room: MoneyInput = 0,
        new_room: MoneyInput = 0,
        unused_contributions: MoneyInput = 0,
        available_room: MoneyInput,
        source: str,
        source_version: str,
    ) -> RegisteredPlanRoom:
        plan = plan_type.strip().upper()
        if plan not in {"RRSP", "TFSA", "FHSA"}:
            raise ValueError("Unsupported registered plan type")
        amounts = tuple(
            to_cents(value)
            for value in (
                deduction_limit,
                unused_deduction_room,
                new_room,
                unused_contributions,
                available_room,
            )
        )
        self._connection.execute(
            """INSERT INTO registered_plan_room_snapshots(
                   person_id, plan_type, effective_year, as_of_date,
                   deduction_limit_cents, unused_deduction_room_cents,
                   new_room_cents, unused_contributions_cents, available_room_cents,
                   source, source_version
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(person_id, plan_type, effective_year) DO UPDATE SET
                   as_of_date = excluded.as_of_date,
                   deduction_limit_cents = excluded.deduction_limit_cents,
                   unused_deduction_room_cents = excluded.unused_deduction_room_cents,
                   new_room_cents = excluded.new_room_cents,
                   unused_contributions_cents = excluded.unused_contributions_cents,
                   available_room_cents = excluded.available_room_cents,
                   source = excluded.source,
                   source_version = excluded.source_version""",
            (person_id, plan, effective_year, as_of_date, *amounts, source, source_version),
        )
        result = self.get(person_id, plan, effective_year)
        if result is None:  # pragma: no cover
            raise RuntimeError("Registered-plan room could not be retrieved")
        return result

    def get(self, person_id: int, plan_type: str, year: int) -> RegisteredPlanRoom | None:
        row = self._connection.execute(
            """SELECT id, person_id, plan_type, effective_year, as_of_date,
                      deduction_limit_cents, unused_deduction_room_cents,
                      new_room_cents, unused_contributions_cents, available_room_cents,
                      source, source_version
                 FROM registered_plan_room_snapshots
                WHERE person_id = ? AND plan_type = ? AND effective_year = ?""",
            (person_id, plan_type, year),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_person(self, person_id: int) -> list[RegisteredPlanRoom]:
        rows = self._connection.execute(
            """SELECT id, person_id, plan_type, effective_year, as_of_date,
                      deduction_limit_cents, unused_deduction_room_cents,
                      new_room_cents, unused_contributions_cents, available_room_cents,
                      source, source_version
                 FROM registered_plan_room_snapshots
                WHERE person_id = ? ORDER BY effective_year DESC, plan_type""",
            (person_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> RegisteredPlanRoom:
        return RegisteredPlanRoom(
            id=RegisteredPlanRoomRepository._required_int(row[0]),
            person_id=RegisteredPlanRoomRepository._required_int(row[1]),
            plan_type=str(row[2]),
            effective_year=RegisteredPlanRoomRepository._required_int(row[3]),
            as_of_date=str(row[4]),
            deduction_limit=from_cents(row[5]),
            unused_deduction_room=from_cents(row[6]),
            new_room=from_cents(row[7]),
            unused_contributions=from_cents(row[8]),
            available_room=from_cents(row[9]),
            source=str(row[10]),
            source_version=str(row[11]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Registered-plan room identifier must be an integer")
        return value
