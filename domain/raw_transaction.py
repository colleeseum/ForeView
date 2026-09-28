from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawTransaction:
    """One immutable source row retained for import provenance and deduplication."""

    id: int
    batch_id: int
    row_number: int
    row_hash: str
    raw_data: str
