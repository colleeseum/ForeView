from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PublicPensionEarning:
    """CPP and QPP pensionable earnings recorded for one year."""

    statement_id: int
    year: int
    qpp_earnings: Decimal
    cpp_earnings: Decimal
    status: str | None
