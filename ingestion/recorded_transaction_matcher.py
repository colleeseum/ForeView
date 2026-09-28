"""Recognise imported rows an account already holds from an earlier import."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from repositories.transaction_repository import TransactionRepository

# A transaction is the same when these values match, unless an importer knows better.
DEFAULT_IDENTITY: tuple[str, ...] = ("transaction_date", "amount", "description")


class RecordedTransactionMatcher:
    """Match an import's rows against the transactions already stored for one account.

    Occurrences are counted rather than just detected: if the account already holds
    two identical transactions and the new file lists three, the first two match and
    the third is new. That makes re-imports and overlapping periods no-ops while
    keeping genuine repeats, such as two identical purchases on the same day.

    When a row carries the balance the institution printed after it, that balance
    is compared as well. It reflects everything before the row, so two identical
    purchases on one day with different balances are recognised as different even
    when an export covers only part of that day.

    Create one matcher per account per import, before writing any of its rows.
    """

    def __init__(
        self,
        transactions: TransactionRepository,
        account_id: int,
        identity: Sequence[str] = DEFAULT_IDENTITY,
    ) -> None:
        self._transactions = transactions
        self._account_id = account_id
        self._identity = tuple(identity)
        self._unmatched: dict[tuple[tuple[str, object], ...], int] = {}

    def is_recorded(self, values: Mapping[str, object]) -> bool:
        """Whether this row matches a stored transaction not yet matched in this import.

        ``values`` maps transaction column names to the row's values. Include
        ``balance_after`` only for a balance printed by the institution.
        """
        columns = self._identity
        if values.get("balance_after") is not None and "balance_after" not in columns:
            columns = (*columns, "balance_after")
        key = tuple((column, values.get(column)) for column in columns)
        if key not in self._unmatched:
            # Counted before this import stores anything with the same key.
            self._unmatched[key] = self._transactions.count_matching(self._account_id, dict(key))
        if self._unmatched[key] > 0:
            self._unmatched[key] -= 1
            return True
        return False
