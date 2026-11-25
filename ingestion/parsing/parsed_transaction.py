# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class ParsedTransaction:
    """One source occurrence, before duplicate matching or balance rebuilding.

    Money is already normalized to cents by the adapter using domain.money.
    source_balance_cents is printed evidence, never a calculated running balance.
    raw_data preserves the adapter's original evidence representation verbatim.
    """

    row_number: int
    transaction_date: str
    amount_cents: int
    raw_data: str = field(repr=False)
    description: str | None = field(default=None, repr=False)
    source_balance_cents: int | None = None
    category: str | None = None
    transaction_type: str = "unclassified"

    def __post_init__(self) -> None:
        if type(self.row_number) is not int or self.row_number < 1:
            raise ValueError("Source row number must be a positive integer")
        if type(self.amount_cents) is not int:
            raise TypeError("Transaction amount must be integer cents")
        if self.source_balance_cents is not None and type(self.source_balance_cents) is not int:
            raise TypeError("Source balance must be integer cents or None")
        if not isinstance(self.transaction_date, str):
            raise TypeError("Transaction date must be ISO date text")
        object.__setattr__(
            self, "transaction_date", date.fromisoformat(self.transaction_date).isoformat()
        )
        for value in (self.raw_data, self.transaction_type):
            if not isinstance(value, str):
                raise TypeError("Source evidence and transaction type must be text")
        for optional_text in (self.description, self.category):
            if optional_text is not None and not isinstance(optional_text, str):
                raise TypeError("Description and category must be text or None")
