# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .payroll_contributions import PayrollContributions


@dataclass(frozen=True, slots=True)
class EmploymentTaxEstimate:
    """Annual employment tax estimate for one Quebec resident."""

    gross_income: Decimal
    taxable_federal_income: Decimal
    taxable_quebec_income: Decimal
    payroll: PayrollContributions
    federal_tax: Decimal
    quebec_tax: Decimal
    rrsp_contribution: Decimal
    rrsp_deduction: Decimal
    rule_year: int

    @property
    def net_income_after_tax(self) -> Decimal:
        return self.gross_income - self.payroll.total - self.federal_tax - self.quebec_tax

    @property
    def disposable_income(self) -> Decimal:
        return self.net_income_after_tax - self.rrsp_contribution
