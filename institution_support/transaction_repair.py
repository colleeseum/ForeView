# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Contract for repairing rows produced by superseded institution parsers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repositories.transaction_repository import TransactionRepository

TransactionRepair = Callable[["TransactionRepository"], int]
