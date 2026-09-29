from __future__ import annotations

import sqlite3
import unittest
from decimal import Decimal

from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.employment_baseline_repository import EmploymentBaselineRepository
from repositories.employment_projection_override_repository import (
    EmploymentProjectionOverrideRepository,
)
from repositories.employment_projection_settings_repository import (
    EmploymentProjectionSettingsRepository,
)
from repositories.person_repository import PersonRepository
from repositories.scenario_repository import ScenarioRepository
from services.database_initialization import ensure_domain_schema


class EmploymentProjectionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        ensure_domain_schema(self.connection)
        self.person_id = PersonRepository(self.connection).create("Alex", "1980-01-15").id
        self.scenario_id = ScenarioRepository(self.connection).create("Baseline", "2026-01-01").id

    def tearDown(self) -> None:
        self.connection.close()

    def test_baseline_is_exact_and_selected_by_effective_date(self) -> None:
        repository = EmploymentBaselineRepository(self.connection)
        repository.upsert(self.person_id, "2025-01-01", "214000.01", "on", "cpp", "T4")
        repository.upsert(self.person_id, "2026-03-01", "220000.02", "QC", "QPP")

        old = repository.get_effective(self.person_id, "2026-02-28")
        current = repository.get_effective(self.person_id, "2026-03-01")

        self.assertEqual(old.annual_salary if old else None, Decimal("214000.01"))
        self.assertEqual(current.annual_salary if current else None, Decimal("220000.02"))
        self.assertEqual(current.province_of_employment if current else None, "QC")
        self.assertEqual(current.payroll_plan if current else None, "QPP")

    def test_actual_derives_gross_and_disposable_without_float(self) -> None:
        actual = AnnualEmploymentActualRepository(self.connection).upsert(
            self.person_id,
            2025,
            "214000.00",
            bonus="14000.00",
            other_income="1600.00",
            rrsp_contribution="31560.00",
            rrsp_deduction="31560.00",
            cpp_qpp="4384.00",
            ei="1049.00",
            qpip="449.54",
            federal_tax="24750.10",
            provincial_tax="33000.20",
            source="T4 and assessments",
        )

        self.assertEqual(actual.gross_income, Decimal("215600.00"))
        self.assertEqual(actual.salary_rate, Decimal("200000.00"))
        self.assertEqual(actual.disposable_income, Decimal("120407.16"))

    def test_settings_preserve_fractional_raise_and_distinct_rrsp_values(self) -> None:
        settings = EmploymentProjectionSettingsRepository(self.connection).upsert(
            self.scenario_id,
            self.person_id,
            default_raise="0.042125",
            retirement_date="2030-07-01",
            recurring_rrsp_contribution="31560.01",
            recurring_rrsp_deduction="30000.02",
            recurring_other_income="1600.03",
        )

        self.assertEqual(settings.default_raise, Decimal("0.042125"))
        self.assertEqual(settings.recurring_rrsp_contribution, Decimal("31560.01"))
        self.assertEqual(settings.recurring_rrsp_deduction, Decimal("30000.02"))

    def test_zero_override_is_distinct_from_no_override(self) -> None:
        repository = EmploymentProjectionOverrideRepository(self.connection)
        override = repository.upsert(
            self.scenario_id,
            self.person_id,
            2030,
            salary=0,
            raise_rate=0,
            rrsp_contribution=0,
        )

        self.assertEqual(override.salary, Decimal("0"))
        self.assertEqual(override.raise_rate, Decimal("0"))
        self.assertIsNone(override.rrsp_deduction)
        self.assertEqual(repository.list_for_person(self.scenario_id, self.person_id), [override])

        repository.delete(self.scenario_id, self.person_id, 2030)
        self.assertIsNone(repository.get(self.scenario_id, self.person_id, 2030))

    def test_invalid_values_are_rejected_before_sql(self) -> None:
        with self.assertRaisesRegex(ValueError, "Payroll plan"):
            EmploymentBaselineRepository(self.connection).upsert(
                self.person_id, "2026-01-01", 1, "QC", "invalid"
            )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            AnnualEmploymentActualRepository(self.connection).upsert(self.person_id, 2026, -1)
        with self.assertRaisesRegex(ValueError, "cannot reduce salary"):
            EmploymentProjectionSettingsRepository(self.connection).upsert(
                self.scenario_id, self.person_id, default_raise="-1.01"
            )


if __name__ == "__main__":
    unittest.main()
