from __future__ import annotations

import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from domain.employment_baseline import EmploymentBaseline
from domain.employment_projection_override import EmploymentProjectionOverride
from domain.employment_projection_settings import EmploymentProjectionSettings
from domain.employment_year_plan import EmploymentYearPlan

_CENT = Decimal("0.01")


class EmploymentIncomeProjector:
    """Resolve salary, raises, retirement proration and annual overrides."""

    def project(
        self,
        baseline: EmploymentBaseline,
        settings: EmploymentProjectionSettings,
        overrides: tuple[EmploymentProjectionOverride, ...],
        *,
        start_year: int,
        end_year: int,
        birth_date: str | None,
        salary_anchor: Decimal | None = None,
        salary_anchor_year: int | None = None,
    ) -> tuple[EmploymentYearPlan, ...]:
        if end_year < start_year:
            raise ValueError("Projection end year cannot precede start year")
        by_year = {item.projection_year: item for item in overrides}
        salary_rate = salary_anchor if salary_anchor is not None else baseline.annual_salary
        anchor_year = salary_anchor_year if salary_anchor_year is not None else start_year
        rows = []
        for year in range(min(start_year, anchor_year + 1), end_year + 1):
            override = by_year.get(year)
            raise_rate = (
                None
                if year == start_year and salary_anchor is None
                else (
                    override.raise_rate
                    if override and override.raise_rate is not None
                    else settings.default_raise
                )
            )
            if year > anchor_year:
                if raise_rate is None:  # pragma: no cover - guarded by year branch
                    raise RuntimeError("Projected year is missing a raise rate")
                salary_rate = self._money(salary_rate * (Decimal("1") + raise_rate))
            if override and override.salary is not None:
                salary_rate = override.salary
            if year < start_year:
                continue
            fraction = self._employment_fraction(year, settings.retirement_date)
            other_income = (
                override.other_income
                if override and override.other_income is not None
                else settings.recurring_other_income
            )
            contribution = (
                override.rrsp_contribution
                if override and override.rrsp_contribution is not None
                else settings.recurring_rrsp_contribution
            )
            deduction = (
                override.rrsp_deduction
                if override and override.rrsp_deduction is not None
                else settings.recurring_rrsp_deduction
            )
            rows.append(
                EmploymentYearPlan(
                    year=year,
                    age=self._age_at_year_end(birth_date, year),
                    annual_salary_rate=self._money(salary_rate),
                    raise_rate=raise_rate,
                    employment_fraction=fraction,
                    salary_income=self._money(salary_rate * fraction),
                    other_income=self._money(other_income * fraction),
                    rrsp_contribution=self._money(contribution),
                    rrsp_deduction=self._money(deduction),
                )
            )
        return tuple(rows)

    @staticmethod
    def _employment_fraction(year: int, retirement_date: str | None) -> Decimal:
        if retirement_date is None:
            return Decimal("1")
        retirement = date.fromisoformat(retirement_date)
        first = date(year, 1, 1)
        after_last = date(year + 1, 1, 1)
        if retirement <= first:
            return Decimal("0")
        if retirement >= after_last:
            return Decimal("1")
        worked_days = (retirement - first).days
        days_in_year = 366 if calendar.isleap(year) else 365
        return Decimal(worked_days) / Decimal(days_in_year)

    @staticmethod
    def _age_at_year_end(birth_date: str | None, year: int) -> int | None:
        if birth_date is None:
            return None
        born = date.fromisoformat(birth_date)
        return year - born.year

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(_CENT, rounding=ROUND_HALF_UP)
