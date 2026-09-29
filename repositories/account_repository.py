from __future__ import annotations

import sqlite3
from typing import Any

from account_types import account_type_registry
from domain.account import Account
from domain.gic_terms import GicTerms
from domain.money import (
    MoneyInput,
    from_cents,
    optional_cents,
    optional_storage_decimal,
    to_cents,
)


class AccountRepository:
    """Persist and retrieve individual accounts rows using SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        name: str | None,
        account_type: str,
        *,
        account_number: str,
        institution: str | None = None,
        tax_treatment: str | None = None,
        asset_kind: str = "account",
        external_provider: str | None = None,
        external_account_id: str | None = None,
        parent_account_id: int | None = None,
        start_date: str | None = None,
        maturity_date: str | None = None,
        maturity_value: MoneyInput | None = None,
        principal: MoneyInput | None = None,
        redeemable: bool = False,
    ) -> Account:
        clean_name, clean_number = self._normalized_identity(
            name,
            account_number,
            asset_kind=asset_kind,
            parent_account_id=parent_account_id,
            maturity_date=maturity_date,
        )
        self._validate(asset_kind, parent_account_id)
        cursor = self._connection.execute(
            """
            INSERT INTO accounts(name, account_number, account_type, institution, tax_treatment,
                                 external_provider, external_account_id, asset_kind,
                                 parent_account_id, start_date, maturity_date, maturity_value,
                                 maturity_value_cents, principal, principal_cents, redeemable)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_name,
                clean_number,
                account_type,
                institution,
                tax_treatment or self._tax_treatment(account_type),
                external_provider,
                external_account_id,
                asset_kind,
                parent_account_id,
                start_date,
                maturity_date,
                optional_storage_decimal(maturity_value),
                optional_cents(maturity_value),
                optional_storage_decimal(principal),
                optional_cents(principal),
                int(redeemable),
            ),
        )
        account = self.get(cursor.lastrowid)
        if account is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Created account could not be retrieved")
        return account

    def update(
        self,
        account_id: int,
        *,
        name: str | None,
        account_number: str,
        institution: str | None,
        category: str | None = None,
        asset_kind: str | None = None,
        external_provider: str | None = None,
        external_account_id: str | None = None,
        parent_account_id: int | None = None,
        start_date: str | None = None,
        maturity_date: str | None = None,
        maturity_value: MoneyInput | None = None,
        principal: MoneyInput | None = None,
        redeemable: bool = False,
    ) -> None:
        normalized_kind = asset_kind or "account"
        clean_name, clean_number = self._normalized_identity(
            name,
            account_number,
            asset_kind=normalized_kind,
            parent_account_id=parent_account_id,
            maturity_date=maturity_date,
        )
        self._validate(asset_kind, parent_account_id)
        if category:
            self._connection.execute(
                """UPDATE accounts SET name = ?, account_number = ?, institution = ?,
                   account_type = ?, external_provider = ?, external_account_id = ?,
                   tax_treatment = ?, asset_kind = COALESCE(?, asset_kind),
                   parent_account_id = ?, start_date = ?, maturity_date = ?,
                   maturity_value = ?, maturity_value_cents = ?, principal = ?,
                   principal_cents = ?, redeemable = ? WHERE id = ?""",
                (
                    clean_name,
                    clean_number,
                    institution,
                    category,
                    external_provider,
                    external_account_id,
                    self._tax_treatment(category),
                    asset_kind,
                    parent_account_id,
                    start_date,
                    maturity_date,
                    optional_storage_decimal(maturity_value),
                    optional_cents(maturity_value),
                    optional_storage_decimal(principal),
                    optional_cents(principal),
                    int(redeemable),
                    account_id,
                ),
            )
        else:
            self._connection.execute(
                """UPDATE accounts SET name = ?, account_number = ?, institution = ?,
                   external_provider = ?, external_account_id = ?,
                   asset_kind = COALESCE(?, asset_kind), parent_account_id = ?,
                   start_date = ?, maturity_date = ?, maturity_value = ?,
                   maturity_value_cents = ?, principal = ?, principal_cents = ?,
                   redeemable = ? WHERE id = ?""",
                (
                    clean_name,
                    clean_number,
                    institution,
                    external_provider,
                    external_account_id,
                    asset_kind,
                    parent_account_id,
                    start_date,
                    maturity_date,
                    optional_storage_decimal(maturity_value),
                    optional_cents(maturity_value),
                    optional_storage_decimal(principal),
                    optional_cents(principal),
                    int(redeemable),
                    account_id,
                ),
            )

    _SELECT = """SELECT id, name, account_number, account_type, institution, tax_treatment,
                       current_interest_rate, asset_kind, parent_account_id,
                       balance_includes_children, start_date, maturity_date, maturity_value_cents,
                       principal_cents, redeemable, external_provider, external_account_id
                FROM accounts"""

    def get(self, account_id: int | None) -> Account | None:
        if account_id is None:
            return None
        return self._one(f"{self._SELECT} WHERE id = ?", (account_id,))  # noqa: S608

    def summary_rows(self) -> list[dict[str, Any]]:
        """Accounts with owners, parent, and latest known balance for the accounts screen."""
        rows = self._connection.execute(
            """
            WITH latest_snapshot AS (
                SELECT account_id, snapshot_date, amount_cents, interest_rate, source_sheet,
                       ROW_NUMBER() OVER (
                           PARTITION BY account_id
                           ORDER BY snapshot_date DESC, id DESC
                       ) AS row_number
                FROM balance_snapshots
            ), latest_transaction AS (
                SELECT account_id, transaction_date, balance_after_cents,
                       ROW_NUMBER() OVER (
                           PARTITION BY account_id
                           ORDER BY transaction_date DESC, id DESC
                       ) AS row_number
                FROM transactions
                WHERE balance_after_cents IS NOT NULL
            )
            SELECT a.id, GROUP_CONCAT(p.name || ' (' || CAST(ROUND(ao.ownership_share * 100, 2) AS TEXT) || '%)') AS owners,
                   GROUP_CONCAT(CAST(ao.person_id AS TEXT) || ':' || CAST(ao.ownership_share AS TEXT)) AS owner_details,
                   a.name, a.account_number, a.institution, a.account_type, a.tax_treatment,
                   a.external_provider, a.external_account_id,
                   a.asset_kind, a.parent_account_id, a.start_date, a.maturity_date,
                   a.maturity_value_cents / 100.0 AS maturity_value,
                   a.principal_cents / 100.0 AS principal,
                   a.redeemable, a.balance_includes_children,
                   parent.name AS parent_name, parent.balance_includes_children AS parent_balance_includes_children,
                   CASE WHEN lt.transaction_date IS NOT NULL
                             AND (s.snapshot_date IS NULL OR lt.transaction_date >= s.snapshot_date)
                        THEN lt.transaction_date
                        ELSE COALESCE(MAX(s.snapshot_date),
                                      CASE WHEN a.asset_kind = 'gic' THEN a.start_date END)
                   END AS latest_date,
                   CASE WHEN lt.transaction_date IS NOT NULL
                             AND (s.snapshot_date IS NULL OR lt.transaction_date >= s.snapshot_date)
                        THEN lt.balance_after_cents
                        ELSE COALESCE(s.amount_cents,
                                      CASE WHEN a.asset_kind = 'gic' THEN a.principal_cents END)
                   END / 100.0 AS latest_amount,
                   COALESCE(a.current_interest_rate, s.interest_rate) AS interest_rate,
                   s.source_sheet
            FROM accounts a
            LEFT JOIN account_owners ao ON ao.account_id = a.id
            LEFT JOIN people p ON p.id = ao.person_id
            LEFT JOIN accounts parent ON parent.id = a.parent_account_id
            LEFT JOIN latest_snapshot s ON s.account_id = a.id AND s.row_number = 1
            LEFT JOIN latest_transaction lt ON lt.account_id = a.id AND lt.row_number = 1
            GROUP BY a.id ORDER BY a.account_type, a.parent_account_id IS NOT NULL, a.name
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def list_ids(self) -> list[int]:
        return [int(row[0]) for row in self._connection.execute("SELECT id FROM accounts")]

    def find_by_external_id(self, provider: str, external_account_id: str) -> Account | None:
        return self._one(
            f"""{self._SELECT}
                WHERE external_provider = ? AND external_account_id = ?
                ORDER BY id LIMIT 1""",  # noqa: S608
            (provider, external_account_id),
        )

    def find_by_institution_number(self, institution: str, account_number: str) -> Account | None:
        return self._one(
            f"""{self._SELECT}
                WHERE institution = ? AND account_number = ?
                ORDER BY id LIMIT 1""",  # noqa: S608
            (institution, account_number),
        )

    def link_external(
        self,
        account_id: int,
        *,
        institution: str,
        provider: str,
        external_account_id: str,
        account_type: str,
    ) -> None:
        """Mark an existing account as the local copy of an institution's account."""
        self._connection.execute(
            """UPDATE accounts SET institution = ?, external_provider = ?,
                   external_account_id = ?, account_type = ?
               WHERE id = ?""",
            (institution, provider, external_account_id, account_type, account_id),
        )

    def gic_children(self, parent_account_id: int) -> list[Account]:
        rows = self._connection.execute(
            f"{self._SELECT} WHERE parent_account_id = ? AND asset_kind = 'gic' ORDER BY id",  # noqa: S608
            (parent_account_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def find_gic_child(
        self,
        parent_account_id: int,
        *,
        name: str,
        certificate_pattern: str | None,
        principal: MoneyInput | None,
        start_date: str | None,
    ) -> Account | None:
        """Find a GIC under a parent by name, certificate, or principal and start date.

        A child whose account number matches the certificate pattern is preferred.
        """
        return self._one(
            f"""{self._SELECT}
                WHERE parent_account_id = ? AND asset_kind = 'gic'
                  AND (name = ? OR account_number LIKE ?
                       OR (principal_cents = ? AND start_date = ?))
                ORDER BY CASE WHEN account_number LIKE ? THEN 0 ELSE 1 END, id
                LIMIT 1""",  # noqa: S608
            (
                parent_account_id,
                name,
                certificate_pattern,
                to_cents(principal) if principal is not None else None,
                start_date,
                certificate_pattern,
            ),
        )

    def find_gic_child_by_certificate(
        self, parent_account_id: int, certificate: str
    ) -> Account | None:
        pattern = f"%{certificate}%"
        return self._one(
            f"""{self._SELECT}
                WHERE parent_account_id = ? AND asset_kind = 'gic'
                  AND (name LIKE ? OR account_number LIKE ?)
                ORDER BY id LIMIT 1""",  # noqa: S608
            (parent_account_id, pattern, pattern),
        )

    def create_gic_child(self, parent: Account, name: str, terms: GicTerms) -> int:
        """Create an imported GIC that inherits its parent's type, institution and tax status.

        Unlike :meth:`create`, the name and account number are stored exactly as given.
        """
        cursor = self._connection.execute(
            """INSERT INTO accounts(
                   name, account_number, account_type, institution, tax_treatment,
                   current_interest_rate, asset_kind, parent_account_id, start_date,
                   maturity_date, maturity_value, maturity_value_cents, principal,
                   principal_cents, redeemable
               ) VALUES (?, ?, ?, ?, ?, ?, 'gic', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                terms.account_number,
                parent.account_type,
                parent.institution,
                parent.tax_treatment,
                terms.interest_rate,
                parent.id,
                terms.start_date,
                terms.maturity_date,
                terms.maturity_value,
                optional_cents(terms.maturity_value),
                terms.principal,
                optional_cents(terms.principal),
                int(terms.redeemable),
            ),
        )
        if cursor.lastrowid is None:  # pragma: no cover - SQLite insert invariant
            raise RuntimeError("Created GIC account has no identifier")
        return cursor.lastrowid

    def update_gic_child(self, child_id: int, parent: Account, terms: GicTerms) -> None:
        """Refresh an imported GIC's terms and re-inherit its parent's classification."""
        self._connection.execute(
            """UPDATE accounts SET account_number = ?, institution = ?, account_type = ?,
               tax_treatment = ?, current_interest_rate = ?, start_date = ?,
               maturity_date = ?, maturity_value = ?, maturity_value_cents = ?,
               principal = ?, principal_cents = ?, redeemable = ?
               WHERE id = ?""",
            (
                terms.account_number,
                parent.institution,
                parent.account_type,
                parent.tax_treatment,
                terms.interest_rate,
                terms.start_date,
                terms.maturity_date,
                terms.maturity_value,
                optional_cents(terms.maturity_value),
                terms.principal,
                optional_cents(terms.principal),
                int(terms.redeemable),
                child_id,
            ),
        )

    def set_balance_includes_children(self, account_id: int, includes_children: bool) -> None:
        self._connection.execute(
            "UPDATE accounts SET balance_includes_children = ? WHERE id = ?",
            (int(includes_children), account_id),
        )

    def rename(self, account_id: int, name: str) -> None:
        self._connection.execute("UPDATE accounts SET name = ? WHERE id = ?", (name, account_id))

    def set_current_interest_rate(self, account_id: int, interest_rate: float | None) -> None:
        if interest_rate is not None and interest_rate < 0:
            raise ValueError("Interest rate cannot be negative")
        self._connection.execute(
            "UPDATE accounts SET current_interest_rate = ? WHERE id = ?",
            (interest_rate, account_id),
        )

    def _one(self, query: str, params: tuple[object, ...]) -> Account | None:
        row = self._connection.execute(query, params).fetchone()
        return self._from_row(row) if row else None

    @staticmethod
    def _normalized_identity(
        name: str | None,
        account_number: str,
        *,
        asset_kind: str,
        parent_account_id: int | None,
        maturity_date: str | None,
    ) -> tuple[str, str]:
        clean_number = account_number.strip()
        clean_name = name.strip() if name and name.strip() else clean_number
        if asset_kind == "gic" and (not clean_number or clean_number.startswith("gic:")):
            clean_number = f"gic:{parent_account_id}:{clean_name}:{maturity_date or 'open'}"
        if not clean_number:
            raise ValueError("Account number is required")
        return clean_name, clean_number

    @staticmethod
    def _validate(asset_kind: str | None, parent_account_id: int | None) -> None:
        if asset_kind is not None and asset_kind not in {"account", "gic"}:
            raise ValueError("Unknown asset kind")
        if asset_kind == "gic" and parent_account_id is None:
            raise ValueError("A GIC must be linked to a parent account")

    @staticmethod
    def _tax_treatment(account_type: str) -> str:
        provider = account_type_registry().find(account_type)
        return provider.tax_treatment if provider else "unspecified"

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> Account:
        account_id = row[0]
        if not isinstance(account_id, int):
            raise TypeError("Account id must be an integer")
        return Account(
            id=account_id,
            name=str(row[1]) if row[1] is not None else None,
            account_number=str(row[2]) if row[2] is not None else None,
            account_type=str(row[3]),
            institution=str(row[4]) if row[4] is not None else None,
            tax_treatment=str(row[5]),
            current_interest_rate=AccountRepository._optional_float(row[6]),
            asset_kind=str(row[7]),
            parent_account_id=AccountRepository._optional_int(row[8]),
            balance_includes_children=bool(row[9]),
            start_date=str(row[10]) if row[10] is not None else None,
            maturity_date=str(row[11]) if row[11] is not None else None,
            maturity_value=AccountRepository._optional_money(row[12]),
            principal=AccountRepository._optional_money(row[13]),
            redeemable=bool(row[14]),
            external_provider=str(row[15]) if row[15] is not None else None,
            external_account_id=str(row[16]) if row[16] is not None else None,
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        if not isinstance(value, (int, float, str)):
            raise TypeError("Account numeric value has an invalid type")
        return float(value)

    @staticmethod
    def _optional_money(value: object) -> float | None:
        return None if value is None else float(from_cents(value))

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        if not isinstance(value, (int, str)):
            raise TypeError("Account identifier has an invalid type")
        return int(value)
