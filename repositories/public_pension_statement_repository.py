# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from domain.money import from_cents, to_cents
from domain.parsed_public_pension_statement import PensionEarningRow, PensionEstimateRow
from domain.public_pension_earning import PublicPensionEarning
from domain.public_pension_estimate import PublicPensionEstimate
from domain.public_pension_statement import PublicPensionStatement


class PublicPensionStatementRepository:
    """Persist an official statement together with its earnings and estimates."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        person_id: int,
        issued_on: str,
        provider: str,
        excludes_second_enhancement: bool,
        source_version: str,
        document_hash: str,
        earnings: Iterable[PensionEarningRow],
        estimates: Iterable[PensionEstimateRow],
    ) -> PublicPensionStatement:
        self._connection.execute(
            """INSERT INTO public_pension_statements(
                   person_id, issued_on, provider, excludes_second_enhancement,
                   source_version, document_hash
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(person_id, provider, issued_on) DO UPDATE SET
                   excludes_second_enhancement = excluded.excludes_second_enhancement,
                   source_version = excluded.source_version,
                   document_hash = excluded.document_hash""",
            (
                person_id,
                issued_on,
                provider,
                int(excludes_second_enhancement),
                source_version,
                document_hash,
            ),
        )
        statement = self.get(person_id, provider, issued_on)
        if statement is None:  # pragma: no cover
            raise RuntimeError("Public pension statement could not be retrieved")
        self._connection.execute(
            "DELETE FROM public_pension_earnings WHERE statement_id = ?", (statement.id,)
        )
        self._connection.execute(
            "DELETE FROM public_pension_estimates WHERE statement_id = ?", (statement.id,)
        )
        self._connection.executemany(
            """INSERT INTO public_pension_earnings(
                   statement_id, year, qpp_earnings_cents, cpp_earnings_cents, status
               ) VALUES (?, ?, ?, ?, ?)""",
            (
                (statement.id, year, to_cents(qpp), to_cents(cpp), status)
                for year, qpp, cpp, status in earnings
            ),
        )
        self._connection.executemany(
            """INSERT INTO public_pension_estimates(
                   statement_id, contribution_assumption, activation_age, monthly_amount_cents
               ) VALUES (?, ?, ?, ?)""",
            (
                (statement.id, assumption, age, to_cents(amount))
                for assumption, age, amount in estimates
            ),
        )
        return statement

    def get(self, person_id: int, provider: str, issued_on: str) -> PublicPensionStatement | None:
        row = self._connection.execute(
            """SELECT id, person_id, issued_on, provider, excludes_second_enhancement,
                      source_version, document_hash
                 FROM public_pension_statements
                WHERE person_id = ? AND provider = ? AND issued_on = ?""",
            (person_id, provider, issued_on),
        ).fetchone()
        return self._statement(row) if row else None

    def latest_for_person(self, person_id: int) -> PublicPensionStatement | None:
        row = self._connection.execute(
            """SELECT id, person_id, issued_on, provider, excludes_second_enhancement,
                      source_version, document_hash
                 FROM public_pension_statements
                WHERE person_id = ? ORDER BY issued_on DESC LIMIT 1""",
            (person_id,),
        ).fetchone()
        return self._statement(row) if row else None

    def earnings(self, statement_id: int) -> list[PublicPensionEarning]:
        rows = self._connection.execute(
            """SELECT statement_id, year, qpp_earnings_cents, cpp_earnings_cents, status
                 FROM public_pension_earnings WHERE statement_id = ? ORDER BY year DESC""",
            (statement_id,),
        ).fetchall()
        return [
            PublicPensionEarning(
                int(r[0]),
                int(r[1]),
                from_cents(r[2]),
                from_cents(r[3]),
                str(r[4]) if r[4] else None,
            )
            for r in rows
        ]

    def estimates(self, statement_id: int) -> list[PublicPensionEstimate]:
        rows = self._connection.execute(
            """SELECT statement_id, contribution_assumption, activation_age, monthly_amount_cents
                 FROM public_pension_estimates
                WHERE statement_id = ? ORDER BY contribution_assumption, activation_age""",
            (statement_id,),
        ).fetchall()
        return [
            PublicPensionEstimate(int(r[0]), str(r[1]), int(r[2]), from_cents(r[3])) for r in rows
        ]

    @staticmethod
    def _statement(row: sqlite3.Row | tuple[object, ...]) -> PublicPensionStatement:
        return PublicPensionStatement(
            id=PublicPensionStatementRepository._required_int(row[0]),
            person_id=PublicPensionStatementRepository._required_int(row[1]),
            issued_on=str(row[2]),
            provider=str(row[3]),
            excludes_second_enhancement=bool(row[4]),
            source_version=str(row[5]),
            document_hash=str(row[6]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Public pension statement identifier must be an integer")
        return value
