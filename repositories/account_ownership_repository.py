from __future__ import annotations

import sqlite3

from domain.account_ownership import AccountOwnership


class AccountOwnershipRepository:
    """Replace and retrieve ownership shares for an account."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace(self, account_id: int, owners: list[tuple[int, float]]) -> None:
        self._validate(owners)
        self._connection.execute("DELETE FROM account_owners WHERE account_id = ?", (account_id,))
        self._connection.executemany(
            """INSERT INTO account_owners(account_id, person_id, ownership_share)
               VALUES (?, ?, ?)""",
            [(account_id, person_id, share) for person_id, share in owners],
        )

    def copy(self, from_account_id: int, to_account_id: int) -> None:
        """Give an account the same owners as another, keeping any it already has."""
        self._connection.execute(
            """INSERT OR IGNORE INTO account_owners(account_id, person_id, ownership_share)
               SELECT ?, person_id, ownership_share FROM account_owners WHERE account_id = ?""",
            (to_account_id, from_account_id),
        )

    def list_for_account(self, account_id: int) -> list[AccountOwnership]:
        rows = self._connection.execute(
            """SELECT account_id, person_id, ownership_share
               FROM account_owners WHERE account_id = ? ORDER BY person_id""",
            (account_id,),
        ).fetchall()
        return [
            AccountOwnership(
                account_id=int(row[0]),
                person_id=int(row[1]),
                share=float(row[2]),
            )
            for row in rows
        ]

    @staticmethod
    def _validate(owners: list[tuple[int, float]]) -> None:
        if not owners:
            raise ValueError("At least one account owner is required")
        total = sum(share for _, share in owners)
        if abs(total - 1.0) > 0.000001:
            raise ValueError("Account ownership shares must total 100%")
        if any(share <= 0 or share > 1 for _, share in owners):
            raise ValueError("Ownership shares must be between 0% and 100%")
