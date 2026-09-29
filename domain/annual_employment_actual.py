from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AnnualEmploymentActual:
    """Historical employment and tax facts for one person and tax year."""

    id: int
    person_id: int
    tax_year: int
    province_of_employment: str | None
    salary_income: Decimal
    bonus: Decimal
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
    def salary_rate(self) -> Decimal:
        return self.salary_income - self.bonus

    @property
    def payroll_plan(self) -> str | None:
        if self.province_of_employment is None:
            return None
        return "QPP" if self.province_of_employment == "QC" else "CPP"

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
