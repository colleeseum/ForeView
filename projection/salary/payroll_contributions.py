from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PayrollContributions:
    """Annual employee payroll contributions split by tax treatment."""

    pension_base: Decimal
    pension_first_additional: Decimal
    pension_second_additional: Decimal
    ei: Decimal
    qpip: Decimal

    @property
    def pension_total(self) -> Decimal:
        return self.pension_base + self.pension_first_additional + self.pension_second_additional

    @property
    def total(self) -> Decimal:
        return self.pension_total + self.ei + self.qpip

    @property
    def pension_deduction(self) -> Decimal:
        return self.pension_first_additional + self.pension_second_additional
