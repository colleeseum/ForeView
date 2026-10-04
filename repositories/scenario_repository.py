# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.scenario import Scenario


class ScenarioRepository:
    """Persist and retrieve projection scenario definitions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        name: str,
        baseline_date: str,
        description: str | None = None,
    ) -> Scenario:
        cursor = self._connection.execute(
            "INSERT INTO scenarios(name, baseline_date, description) VALUES (?, ?, ?)",
            (name.strip(), baseline_date, description),
        )
        scenario = self.get(cursor.lastrowid)
        if scenario is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created scenario could not be retrieved")
        return scenario

    def get(self, scenario_id: int | None) -> Scenario | None:
        if scenario_id is None:
            return None
        row = self._connection.execute(
            "SELECT id, name, baseline_date, description FROM scenarios WHERE id = ?",
            (scenario_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_all(self) -> list[Scenario]:
        rows = self._connection.execute(
            "SELECT id, name, baseline_date, description FROM scenarios ORDER BY id"
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> Scenario:
        scenario_id = row[0]
        if not isinstance(scenario_id, int):
            raise TypeError("Scenario id must be an integer")
        return Scenario(
            id=scenario_id,
            name=str(row[1]),
            baseline_date=str(row[2]),
            description=str(row[3]) if row[3] is not None else None,
        )
