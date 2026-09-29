from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AnnualEmploymentActual:
    """Historical employment and tax facts for one person and tax year."""

    id: int
    person_id: int
    tax_year: int
    salary_income: Decimal
    other_income: Decimal
    rrsp_contribution: Decimal
    rrsp_deduction: Decimal
    cpp_qpp: Decimal
    ei: Decimal
    qpip: Decimal
    federal_tax: Decimal
    provincial_tax: Decimal
    source: str | None

    @property
    def gross_income(self) -> Decimal:
        return self.salary_income + self.other_income

    @property
    def disposable_income(self) -> Decimal:
        return (
            self.gross_income
            - self.cpp_qpp
            - self.ei
            - self.qpip
            - self.federal_tax
            - self.provincial_tax
            - self.rrsp_contribution
        )
