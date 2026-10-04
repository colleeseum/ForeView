# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Repair transaction rows produced by superseded EQ parsers."""

from __future__ import annotations

import json
import re

from repositories.transaction_repository import TransactionRepository

from .raw_sources import EQ_PDF

_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DATE_LINE = re.compile(rf"^({_MONTHS})\s+(\d{{1,2}})\s+(.+)$")
_MONEY = re.compile(r"\$[\d,]+\.\d{2}")


def repair_transactions(transactions: TransactionRepository) -> int:
    repaired = 0
    for transaction_id, _description, raw_data in transactions.descriptions_from_source(
        EQ_PDF, blank_only=True
    ):
        data = json.loads(raw_data)
        raw_line = data.get("raw_line", "")
        match = _DATE_LINE.match(raw_line.strip())
        money = list(_MONEY.finditer(raw_line))
        if not match or len(money) < 2:
            continue
        description = re.sub(r"-\s*$", "", raw_line[match.start(3) : money[-2].start()]).strip()
        transactions.update_description(transaction_id, description)
        repaired += 1
    return repaired
