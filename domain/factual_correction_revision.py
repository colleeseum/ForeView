from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FactualCorrectionRevision:
    """One immutable revision of a consolidated factual correction."""

    id: int
    person_id: int
    tax_year: int
    concept: str
    revision_number: int
    revision_kind: str
    correct_amount: Decimal | None
    reason: str
    source_at_correction_id: int | None
    source_document_kind: str | None
    source_jurisdiction: str | None
    source_concept: str | None
    source_description: str | None
    source_reported_amount: Decimal | None
    source_determined_amount: Decimal | None
    source_line_code: str | None
    source_name: str
    source_version: str | None
    source_document_hash: str | None
    fingerprint: str
    created_at: str

    @property
    def is_active(self) -> bool:
        return self.revision_kind != "remove"
