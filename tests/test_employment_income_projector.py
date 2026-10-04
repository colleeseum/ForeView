# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import unittest
from decimal import Decimal

from domain.employment_projection_override import EmploymentProjectionOverride
from domain.employment_projection_settings import EmploymentProjectionSettings
from projection.salary import EmploymentIncomeProjector


class EmploymentIncomeProjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = EmploymentProjectionSettings(
            scenario_id=3,
            person_id=2,
            default_raise=Decimal("0.04"),
            retirement_date=None,
            recurring_rrsp_contribution=Decimal("10000"),
            recurring_rrsp_deduction=Decimal("9000"),
            recurring_other_income=Decimal("1000"),
        )

    def test_salary_and_raise_overrides_propagate_to_later_years(self) -> None:
        overrides = (
            EmploymentProjectionOverride(3, 2, 2027, raise_rate=Decimal("0.10")),
            EmploymentProjectionOverride(3, 2, 2028, salary=Decimal("150000")),
        )

        rows = EmploymentIncomeProjector().project(
            Decimal("100000"),
            2026,
            self.settings,
            overrides,
            start_year=2026,
            end_year=2029,
            birth_date="1980-04-15",
        )

        self.assertEqual(
            [row.annual_salary_rate for row in rows],
            [
                Decimal("100000.00"),
                Decimal("110000.00"),
                Decimal("150000.00"),
                Decimal("156000.00"),
            ],
        )
        self.assertEqual(rows[-1].age, 49)

    def test_retirement_is_first_non_working_day_and_rrsp_is_not_prorated(self) -> None:
        settings = EmploymentProjectionSettings(
            scenario_id=3,
            person_id=2,
            default_raise=Decimal("0"),
            retirement_date="2028-07-01",
            recurring_rrsp_contribution=Decimal("10000"),
            recurring_rrsp_deduction=Decimal("9000"),
            recurring_other_income=Decimal("12000"),
        )

        rows = EmploymentIncomeProjector().project(
            Decimal("100000"),
            2028,
            settings,
            (),
            start_year=2028,
            end_year=2029,
            birth_date=None,
        )

        self.assertEqual(rows[0].employment_fraction, Decimal("182") / Decimal("366"))
        self.assertEqual(rows[0].salary_income, Decimal("49726.78"))
        self.assertEqual(rows[0].other_income, Decimal("5967.21"))
        self.assertEqual(rows[0].rrsp_contribution, Decimal("10000.00"))
        self.assertEqual(rows[1].employment_fraction, Decimal("0"))
        self.assertEqual(rows[1].salary_income, Decimal("0.00"))

    def test_zero_override_is_applied_instead_of_default(self) -> None:
        override = EmploymentProjectionOverride(
            3,
            2,
            2026,
            rrsp_contribution=Decimal("0"),
            rrsp_deduction=Decimal("0"),
            other_income=Decimal("0"),
        )

        row = EmploymentIncomeProjector().project(
            Decimal("100000"),
            2026,
            self.settings,
            (override,),
            start_year=2026,
            end_year=2026,
            birth_date=None,
        )[0]

        self.assertEqual(row.rrsp_contribution, Decimal("0.00"))
        self.assertEqual(row.rrsp_deduction, Decimal("0.00"))
        self.assertEqual(row.other_income, Decimal("0.00"))

    def test_factual_salary_anchor_compounds_through_hidden_years(self) -> None:
        rows = EmploymentIncomeProjector().project(
            Decimal("100000"),
            2024,
            self.settings,
            (),
            start_year=2026,
            end_year=2027,
            birth_date=None,
        )

        self.assertEqual(
            [row.annual_salary_rate for row in rows],
            [Decimal("108160.00"), Decimal("112486.40")],
        )
        self.assertEqual(rows[0].raise_rate, Decimal("0.04"))


if __name__ == "__main__":
    unittest.main()
