# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.scenario_assumption import ScenarioAssumption


class ScenarioAssumptionRepository:
    """Replace and retrieve assumptions identified by scenario and key."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def set(
        self,
        scenario_id: int,
        key: str,
        value: str,
        unit: str | None = None,
    ) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO scenario_assumptions(scenario_id, key, value, unit)
            VALUES (?, ?, ?, ?)
            """,
            (scenario_id, key, value, unit),
        )

    def get(self, scenario_id: int, key: str) -> ScenarioAssumption | None:
        row = self._connection.execute(
            """SELECT scenario_id, key, value, unit
               FROM scenario_assumptions WHERE scenario_id = ? AND key = ?""",
            (scenario_id, key),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_scenario(self, scenario_id: int) -> list[ScenarioAssumption]:
        rows = self._connection.execute(
            """SELECT scenario_id, key, value, unit
               FROM scenario_assumptions WHERE scenario_id = ? ORDER BY key""",
            (scenario_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> ScenarioAssumption:
        scenario_id = row[0]
        if not isinstance(scenario_id, int):
            raise TypeError("Scenario assumption scenario id must be an integer")
        return ScenarioAssumption(
            scenario_id=scenario_id,
            key=str(row[1]),
            value=str(row[2]),
            unit=str(row[3]) if row[3] is not None else None,
        )
