# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Run institution-owned repairs for rows produced by superseded parsers."""

from __future__ import annotations

import sqlite3

from institution_support.registry import institution_registry
from repositories.transaction_repository import TransactionRepository


class ImportedTransactionRepair:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._transactions = TransactionRepository(connection)

    def execute(self) -> int:
        repaired = sum(
            provider.transaction_repair(self._transactions)
            for provider in institution_registry().providers
            if provider.transaction_repair is not None
        )
        if repaired:
            self._connection.commit()
        return repaired
