from __future__ import annotations

import sqlite3


class MonetaryCentsMigration:
    """Add exact integer-cent storage beside legacy REAL monetary columns."""

    version = 3
    name = "monetary_cents"

    _COLUMNS = {
        "accounts": ("maturity_value", "principal"),
        "balance_snapshots": ("amount", "contribution"),
        "fixed_term_deposits": ("principal", "maturity_value"),
        "statement_reconciliations": (
            "opening_balance",
            "closing_balance",
            "statement_deposits",
            "statement_withdrawals",
            "csv_net_change",
            "difference",
        ),
        "investment_holdings": ("market_value",),
        "real_estate_assets": ("estimated_value", "acb"),
        "real_estate_projections": ("projected_value", "projected_acb"),
        "reconciliation_checkpoints": ("closing_balance", "net_change", "difference"),
        "transactions": ("amount", "balance_after"),
    }

    def apply(self, connection: sqlite3.Connection) -> None:
        for table, columns in self._COLUMNS.items():
            existing = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
            for column in columns:
                cents = f"{column}_cents"
                if cents not in existing:
                    connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN {cents} INTEGER"  # noqa: S608
                    )
                connection.execute(
                    f"UPDATE {table} SET {cents} = {self._sql_cents(column)} "  # nosec
                    f"WHERE {column} IS NOT NULL AND {cents} IS NULL"  # noqa: S608
                )
                self._create_compatibility_triggers(connection, table, column, cents)

    @staticmethod
    def _create_compatibility_triggers(
        connection: sqlite3.Connection, table: str, column: str, cents: str
    ) -> None:
        insert_trigger = f"sync_{table}_{column}_cents_insert"
        update_trigger = f"sync_{table}_{column}_cents_update"
        cents_expression = MonetaryCentsMigration._sql_cents(f"NEW.{column}")
        connection.execute(
            f"""CREATE TRIGGER IF NOT EXISTS {insert_trigger}
                AFTER INSERT ON {table}
                WHEN NEW.{column} IS NOT NULL AND NEW.{cents} IS NULL
                BEGIN
                    UPDATE {table}
                    SET {cents} = {cents_expression}
                    WHERE rowid = NEW.rowid;
                END"""  # noqa: S608  # nosec
        )
        connection.execute(
            f"""CREATE TRIGGER IF NOT EXISTS {update_trigger}
                AFTER UPDATE OF {column} ON {table}
                WHEN NEW.{cents} IS OLD.{cents}
                BEGIN
                    UPDATE {table}
                    SET {cents} = CASE WHEN NEW.{column} IS NULL THEN NULL
                                      ELSE {cents_expression} END
                    WHERE rowid = NEW.rowid;
                END"""  # noqa: S608  # nosec
        )

    @staticmethod
    def _sql_cents(value: str) -> str:
        """SQLite REAL compatibility conversion; application writes use Decimal directly."""
        epsilon = f"CASE WHEN {value} < 0 THEN -0.000000001 ELSE 0.000000001 END"
        return f"CAST(ROUND(({value} + {epsilon}) * 100) AS INTEGER)"
