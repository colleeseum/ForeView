from __future__ import annotations

import sqlite3

from domain.money import from_cents, optional_cents
from domain.statement_reconciliation import StatementReconciliation


class StatementReconciliationRepository:
    """Persist and retrieve statement-to-transaction comparisons."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        account_id: int,
        import_batch_id: int,
        statement_start: str,
        statement_end: str,
        *,
        opening_balance: float | None,
        closing_balance: float | None,
        statement_deposits: float | None,
        statement_withdrawals: float | None,
        csv_transaction_count: int,
        csv_net_change: float | None,
        difference: float | None,
        status: str,
    ) -> StatementReconciliation:
        cursor = self._connection.execute(
            """
            INSERT INTO statement_reconciliations(
                account_id, import_batch_id, statement_start, statement_end,
                opening_balance, closing_balance, statement_deposits, statement_withdrawals,
                opening_balance_cents, closing_balance_cents, statement_deposits_cents,
                statement_withdrawals_cents, csv_transaction_count, csv_net_change,
                csv_net_change_cents, difference, difference_cents, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                import_batch_id,
                statement_start,
                statement_end,
                opening_balance,
                closing_balance,
                statement_deposits,
                statement_withdrawals,
                optional_cents(opening_balance),
                optional_cents(closing_balance),
                optional_cents(statement_deposits),
                optional_cents(statement_withdrawals),
                csv_transaction_count,
                csv_net_change,
                optional_cents(csv_net_change),
                difference,
                optional_cents(difference),
                status,
            ),
        )
        reconciliation = self.get(cursor.lastrowid)
        if reconciliation is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created statement reconciliation could not be retrieved")
        return reconciliation

    def get(self, reconciliation_id: int | None) -> StatementReconciliation | None:
        if reconciliation_id is None:
            return None
        row = self._connection.execute(
            f"{self._SELECT} WHERE id = ?",  # noqa: S608 - static query fragment
            (reconciliation_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def get_by_import_batch(self, import_batch_id: int) -> StatementReconciliation | None:
        row = self._connection.execute(
            f"{self._SELECT} WHERE import_batch_id = ?",  # noqa: S608 - static query fragment
            (import_batch_id,),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_account(self, account_id: int) -> list[StatementReconciliation]:
        rows = self._connection.execute(
            f"{self._SELECT} WHERE account_id = ? ORDER BY statement_start, id",  # noqa: S608
            (account_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    _SELECT = """SELECT id, account_id, import_batch_id, statement_start, statement_end,
                         opening_balance_cents, closing_balance_cents,
                         statement_deposits_cents, statement_withdrawals_cents,
                         csv_transaction_count, csv_net_change_cents,
                         difference_cents, status, created_at
                  FROM statement_reconciliations"""

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> StatementReconciliation:
        reconciliation_id = StatementReconciliationRepository._required_int(row[0])
        account_id = StatementReconciliationRepository._required_int(row[1])
        import_batch_id = StatementReconciliationRepository._required_int(row[2])
        csv_transaction_count = StatementReconciliationRepository._required_int(row[9])
        return StatementReconciliation(
            id=reconciliation_id,
            account_id=account_id,
            import_batch_id=import_batch_id,
            statement_start=str(row[3]),
            statement_end=str(row[4]),
            opening_balance=StatementReconciliationRepository._optional_money(row[5]),
            closing_balance=StatementReconciliationRepository._optional_money(row[6]),
            statement_deposits=StatementReconciliationRepository._optional_money(row[7]),
            statement_withdrawals=StatementReconciliationRepository._optional_money(row[8]),
            csv_transaction_count=csv_transaction_count,
            csv_net_change=StatementReconciliationRepository._optional_money(row[10]),
            difference=StatementReconciliationRepository._optional_money(row[11]),
            status=str(row[12]),
            created_at=str(row[13]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Statement reconciliation identifiers and count must be integers")
        return value

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        if not isinstance(value, (int, float, str)):
            raise TypeError("Statement reconciliation numeric value has an invalid type")
        return float(value)

    @staticmethod
    def _optional_money(value: object) -> float | None:
        return None if value is None else float(from_cents(value))
