from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImportBatch:
    """One immutable record of an imported file or external activity stream."""

    id: int
    account_id: int | None
    filename: str
    file_hash: str
    imported_at: str
    row_count: int
