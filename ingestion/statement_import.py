# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Helpers shared by institution statement importers."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from domain.import_batch import ImportBatch


def unrecognized_pdf(institution: str) -> ValueError:
    return ValueError(
        f'Unrecognized PDF format for institution "{institution}". See transaction import help.'
    )


def account_digits(value: object) -> str:
    """Digits of an account number, for comparing statement and stored numbers."""
    return re.sub(r"\D", "", str(value or ""))


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def already_imported(batch: ImportBatch) -> dict[str, Any]:
    return {
        "batch_id": batch.id,
        "imported": 0,
        "duplicates": batch.row_count,
        "status": "already_imported",
    }
