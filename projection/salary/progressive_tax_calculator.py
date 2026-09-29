from __future__ import annotations

from decimal import Decimal

from projection.public_rules import TaxBracketSchedule


class ProgressiveTaxCalculator:
    """Apply a bracket schedule to non-negative taxable income."""

    def calculate(self, taxable_income: Decimal, schedule: TaxBracketSchedule) -> Decimal:
        remaining = max(taxable_income, Decimal("0"))
        lower = Decimal("0")
        tax = Decimal("0")
        for bracket in schedule.brackets:
            if bracket.upper_bound is None:
                taxable_slice = remaining
            else:
                taxable_slice = min(remaining, bracket.upper_bound - lower)
            if taxable_slice > 0:
                tax += taxable_slice * bracket.rate
                remaining -= taxable_slice
            if remaining <= 0 or bracket.upper_bound is None:
                break
            lower = bracket.upper_bound
        return tax
