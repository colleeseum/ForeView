from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ParsedAnnualEmploymentActual:
    """Common factual annual-employment values returned by an import source."""

    tax_year: int
    employment_income: Decimal
    other_employment_income: Decimal
    cpp_qpp: Decimal
    ei: Decimal
    qpip: Decimal
    rrsp_contribution: Decimal
    rrsp_deduction: Decimal
    federal_tax: Decimal
    provincial_tax: Decimal
    province_of_employment: str | None = None
    taxpayer_name: str | None = None
