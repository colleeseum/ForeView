from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from domain.parsed_annual_employment_actual import ParsedAnnualEmploymentActual

IncomeParser = Callable[[bytes], ParsedAnnualEmploymentActual]


@dataclass(frozen=True, slots=True)
class IncomeSourceProvider:
    """Contract for one source of factual annual-employment records."""

    key: str
    display_name: str
    parser: IncomeParser
    source_label: str
    help_text: str
    last_changed: str
