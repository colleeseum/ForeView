from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PensionEarningRow = tuple[int, Decimal, Decimal, str | None]
PensionEstimateRow = tuple[str, int, Decimal]


@dataclass(frozen=True, slots=True)
class ParsedPublicPensionStatement:
    """Values extracted from an official CPP/QPP participation statement."""

    issued_on: str
    taxpayer_name: str | None
    birth_date: str | None
    provider: str
    excludes_second_enhancement: bool
    earnings: tuple[PensionEarningRow, ...]
    estimates: tuple[PensionEstimateRow, ...]
