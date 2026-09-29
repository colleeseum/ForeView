from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ParsedUFileTaxReturn:
    """Annual factual values read from one taxpayer's UFile return."""

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
