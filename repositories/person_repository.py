# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.person import Person


class PersonRepository:
    """Persist and retrieve immutable Person objects using SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(self, name: str, birth_date: str | None = None) -> Person:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Person name is required")
        self._connection.execute(
            "INSERT INTO people(name, birth_date) VALUES (?, ?)",
            (clean_name, birth_date or None),
        )
        person = self.find_by_name(clean_name)
        if person is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created person could not be retrieved")
        return person

    def get(self, person_id: int) -> Person | None:
        row = self._connection.execute(
            "SELECT id, name, birth_date FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        return self._from_row(row) if row else None

    def find_by_name(self, name: str) -> Person | None:
        row = self._connection.execute(
            "SELECT id, name, birth_date FROM people WHERE name = ?", (name,)
        ).fetchone()
        return self._from_row(row) if row else None

    def find_or_create(self, name: str | None) -> Person | None:
        """Resolve an imported owner name while preserving legacy spelling."""
        if not name:
            return None
        self._connection.execute("INSERT OR IGNORE INTO people(name) VALUES (?)", (name,))
        return self.find_by_name(name)

    def list_all(self) -> list[Person]:
        rows = self._connection.execute(
            "SELECT id, name, birth_date FROM people ORDER BY name"
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_birth_date(self, person_id: int, birth_date: str) -> None:
        self._connection.execute(
            "UPDATE people SET birth_date = ? WHERE id = ?", (birth_date, person_id)
        )

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> Person:
        person_id = row[0]
        if not isinstance(person_id, int):
            raise TypeError("Person id must be an integer")
        return Person(
            id=person_id,
            name=str(row[1]),
            birth_date=str(row[2]) if row[2] else None,
        )
