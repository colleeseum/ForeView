# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CsvLedgerRow:
    """Stored matching facts with authoritative integer-cent money."""

    transaction_date: str
    amount_cents: int
    description: str | None = field(repr=False)
    balance_after_cents: int | None
