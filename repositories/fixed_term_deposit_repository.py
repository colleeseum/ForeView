# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.fixed_term_deposit import FixedTermDeposit
from domain.money import (
    MoneyInput,
    as_decimal,
    from_cents,
    optional_cents,
    optional_storage_decimal,
    storage_decimal,
    to_cents,
)


class FixedTermDepositRepository:
    """Persist and retrieve legacy fixed-term deposit rows."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        account_id: int,
        name: str,
        principal: MoneyInput,
        interest_rate: float,
        start_date: str,
        maturity_date: str,
        *,
        redeemable: bool = False,
        renewal_rule: str = "cash_at_maturity",
        maturity_value: MoneyInput | None = None,
        source_filename: str | None = None,
    ) -> FixedTermDeposit:
        self._validate(principal, interest_rate, start_date, maturity_date)
        cursor = self._connection.execute(
            """
            INSERT INTO fixed_term_deposits(
                account_id, name, principal, interest_rate, start_date, maturity_date,
                principal_cents, maturity_value, maturity_value_cents,
                source_filename, redeemable, renewal_rule
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                name.strip(),
                storage_decimal(principal),
                interest_rate,
                start_date,
                maturity_date,
                to_cents(principal),
                optional_storage_decimal(maturity_value),
                optional_cents(maturity_value),
                source_filename,
                int(redeemable),
                renewal_rule,
            ),
        )
        deposit = self.get(cursor.lastrowid)
        if deposit is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created fixed-term deposit could not be retrieved")
        return deposit

    def get(self, deposit_id: int | None) -> FixedTermDeposit | None:
        if deposit_id is None:
            return None
        row = self._connection.execute(
            """SELECT id, account_id, name, principal_cents, interest_rate, start_date,
                      maturity_date, maturity_value_cents, source_filename, redeemable, renewal_rule
               FROM fixed_term_deposits WHERE id = ?""",
            (deposit_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def upsert_imported(
        self,
        account_id: int,
        name: str,
        principal: MoneyInput,
        interest_rate: float,
        start_date: str,
        maturity_date: str,
        *,
        maturity_value: MoneyInput | None,
        source_filename: str,
        redeemable: bool,
    ) -> FixedTermDeposit:
        existing = self._connection.execute(
            """SELECT id FROM fixed_term_deposits
               WHERE account_id = ?
                 AND (name = ? OR (principal_cents = ? AND start_date = ? AND maturity_date = ?))
               ORDER BY id LIMIT 1""",
            (account_id, name, to_cents(principal), start_date, maturity_date),
        ).fetchone()
        if existing:
            deposit_id = int(existing[0])
            self._connection.execute(
                """UPDATE fixed_term_deposits
                   SET principal = ?, interest_rate = ?, start_date = ?, maturity_date = ?,
                       principal_cents = ?, maturity_value = ?, maturity_value_cents = ?,
                       source_filename = ?, redeemable = ?
                   WHERE id = ?""",
                (
                    storage_decimal(principal),
                    interest_rate,
                    start_date,
                    maturity_date,
                    to_cents(principal),
                    optional_storage_decimal(maturity_value),
                    optional_cents(maturity_value),
                    source_filename,
                    int(redeemable),
                    deposit_id,
                ),
            )
        else:
            cursor = self._connection.execute(
                """INSERT INTO fixed_term_deposits(
                       account_id, name, principal, interest_rate, start_date, maturity_date,
                       principal_cents, maturity_value, maturity_value_cents,
                       source_filename, redeemable
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    name,
                    storage_decimal(principal),
                    interest_rate,
                    start_date,
                    maturity_date,
                    to_cents(principal),
                    optional_storage_decimal(maturity_value),
                    optional_cents(maturity_value),
                    source_filename,
                    int(redeemable),
                ),
            )
            inserted_id = cursor.lastrowid
            if inserted_id is None:  # pragma: no cover - SQLite insert invariant
                raise RuntimeError("Imported fixed-term deposit has no identifier")
            deposit_id = inserted_id
        deposit = self.get(deposit_id)
        if deposit is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Imported fixed-term deposit could not be retrieved")
        return deposit

    def list_for_account(self, account_id: int) -> list[FixedTermDeposit]:
        rows = self._connection.execute(
            """SELECT id, account_id, name, principal_cents, interest_rate, start_date,
                      maturity_date, maturity_value_cents, source_filename, redeemable, renewal_rule
               FROM fixed_term_deposits
               WHERE account_id = ? ORDER BY maturity_date, id""",
            (account_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_all(self) -> list[FixedTermDeposit]:
        rows = self._connection.execute(
            """SELECT id, account_id, name, principal_cents, interest_rate, start_date,
                      maturity_date, maturity_value_cents, source_filename, redeemable, renewal_rule
               FROM fixed_term_deposits ORDER BY id"""
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _validate(
        principal: MoneyInput,
        interest_rate: float,
        start_date: str,
        maturity_date: str,
    ) -> None:
        if as_decimal(principal) < 0:
            raise ValueError("GIC principal cannot be negative")
        if interest_rate < 0:
            raise ValueError("GIC interest rate cannot be negative")
        if maturity_date < start_date:
            raise ValueError("GIC maturity date cannot precede its start date")

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> FixedTermDeposit:
        deposit_id = row[0]
        account_id = row[1]
        if not isinstance(deposit_id, int) or not isinstance(account_id, int):
            raise TypeError("Fixed-term deposit identifiers must be integers")
        return FixedTermDeposit(
            id=deposit_id,
            account_id=account_id,
            name=str(row[2]),
            principal=float(from_cents(row[3])),
            interest_rate=FixedTermDepositRepository._required_float(row[4]),
            start_date=str(row[5]),
            maturity_date=str(row[6]),
            maturity_value=None if row[7] is None else float(from_cents(row[7])),
            source_filename=str(row[8]) if row[8] is not None else None,
            redeemable=bool(row[9]),
            renewal_rule=str(row[10]),
        )

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("Fixed-term deposit numeric value has an invalid type")
        return float(value)

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        return FixedTermDepositRepository._required_float(value)
