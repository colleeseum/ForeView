"""Whether a raw imported row carries a balance printed by the institution."""

from __future__ import annotations

import json
from collections.abc import Collection

# Header names that mark a CSV column as a bank-reported running balance.
CSV_BALANCE_COLUMNS = ("balance", "running balance")


def has_bank_reported_balance(raw_data: str | None, statement_sources: Collection[str]) -> bool:
    """Return whether a raw row carries a balance printed by the institution.

    ``statement_sources`` are the tags institutions declare for statement rows,
    which store that balance in their ``balance`` field; other rows are CSV rows.
    """
    if not raw_data:
        return False
    try:
        parsed = json.loads(raw_data)
    except (TypeError, json.JSONDecodeError):
        return False
    if parsed.get("source") in statement_sources:
        return parsed.get("balance") is not None
    return any(
        str(key).strip().lower() in CSV_BALANCE_COLUMNS and value not in (None, "")
        for key, value in parsed.items()
    )
