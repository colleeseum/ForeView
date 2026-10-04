from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ResolvedIncomeSource:
    """The source-based value that wins precedence for one annual concept."""

    id: int | None
    concept: str
    description: str
    document_kind: str | None
    jurisdiction: str | None
    reported_amount: Decimal | None
    determined_amount: Decimal | None
    line_code: str | None
    source: str
    source_version: str | None
    document_hash: str | None

    @property
    def amount(self) -> Decimal | None:
        if self.determined_amount is not None:
            return self.determined_amount
        return self.reported_amount

    @property
    def has_value(self) -> bool:
        return self.amount is not None

    @classmethod
    def absent(cls, concept: str, description: str) -> ResolvedIncomeSource:
        return cls(
            id=None,
            concept=concept,
            description=description,
            document_kind=None,
            jurisdiction=None,
            reported_amount=None,
            determined_amount=None,
            line_code=None,
            source="No underlying value",
            source_version=None,
            document_hash=None,
        )
