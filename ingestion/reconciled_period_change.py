"""Raised when an import would add transactions to a reconciled period."""

from __future__ import annotations


class ReconciledPeriodChange(Exception):
    """An import would change an account's already-reconciled ledger.

    Not a ``ValueError``: callers must handle it explicitly by asking the user.
    """

    def __init__(self, account_id: int, reconciled_through: str, transaction_count: int) -> None:
        self.account_id = account_id
        self.reconciled_through = reconciled_through
        self.transaction_count = transaction_count
        super().__init__(
            f"This account is reconciled through {reconciled_through}. Importing would add "
            f"{transaction_count} transaction{'s' if transaction_count != 1 else ''} to that period."
        )
