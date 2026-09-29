from __future__ import annotations

import sqlite3
import unittest
from decimal import Decimal
from pathlib import Path

from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.employment_baseline_repository import EmploymentBaselineRepository
from repositories.employment_projection_settings_repository import (
    EmploymentProjectionSettingsRepository,
)
from repositories.person_repository import PersonRepository
from repositories.public_rule_approval_repository import PublicRuleApprovalRepository
from repositories.scenario_repository import ScenarioRepository
from services.database_initialization import ensure_domain_schema
from services.public_rule_catalog import PublicRuleCatalog
from services.salary_projection_service import SalaryProjectionService


class SalaryProjectionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        ensure_domain_schema(self.connection)
        self.person_id = PersonRepository(self.connection).create("Alex", "1980-04-15").id
        self.scenario_id = ScenarioRepository(self.connection).create("Baseline", "2026-01-01").id
        EmploymentBaselineRepository(self.connection).upsert(
            self.person_id, "2026-01-01", 100000, "ON", "CPP", "manual"
        )
        EmploymentProjectionSettingsRepository(self.connection).upsert(
            self.scenario_id,
            self.person_id,
            default_raise="0.04",
            recurring_rrsp_contribution=10000,
            recurring_rrsp_deduction=10000,
        )
        self.catalog = PublicRuleCatalog(Path("public_rules"))

    def tearDown(self) -> None:
        self.connection.close()

    def _approve_2026(self) -> None:
        repository = PublicRuleApprovalRepository(self.connection)
        for rule_set_id in (
            "ca-2026-official",
            "ca-qc-2026-official",
            "ca-on-2026-official",
        ):
            package = self.catalog.get(rule_set_id)
            self.assertIsNotNone(package)
            repository.approve(rule_set_id, package.content_hash)  # type: ignore[union-attr]

    def test_projection_requires_exact_rule_hash_approval(self) -> None:
        with self.assertRaisesRegex(ValueError, "Approve public rules ca-2026-official"):
            SalaryProjectionService(self.connection, Path("public_rules")).project_person(
                self.scenario_id, self.person_id, 2026, 2026
            )

    def test_future_years_hold_latest_approved_rules_constant(self) -> None:
        self._approve_2026()

        rows = SalaryProjectionService(self.connection, Path("public_rules")).project_person(
            self.scenario_id, self.person_id, 2026, 2027
        )

        self.assertEqual(rows[0].annual_salary_rate, Decimal("100000.00"))
        self.assertFalse(rows[0].rules_held_constant)
        self.assertEqual(rows[1].annual_salary_rate, Decimal("104000.00"))
        self.assertEqual(rows[1].rule_year, 2026)
        self.assertTrue(rows[1].rules_held_constant)
        self.assertGreater(rows[1].disposable_income, Decimal("0"))

    def test_latest_factual_income_salary_rate_replaces_baseline_salary(self) -> None:
        self._approve_2026()
        AnnualEmploymentActualRepository(self.connection).upsert(
            self.person_id,
            2025,
            "105000",
            province_of_residence="QC",
            payroll_plan="QPP",
            bonus="5000",
            other_income="300",
            rrsp_contribution="5000",
            rrsp_deduction="4000",
        )

        rows = SalaryProjectionService(self.connection, Path("public_rules")).project_person(
            self.scenario_id, self.person_id, 2026, 2026
        )

        self.assertEqual(rows[0].annual_salary_rate, Decimal("104000.00"))
        self.assertEqual(rows[0].raise_rate, Decimal("0.04"))
        self.assertGreater(rows[0].qpip, Decimal("0"))
        self.assertEqual(rows[0].other_income, Decimal("300.00"))
        self.assertEqual(rows[0].rrsp_contribution, Decimal("5000.00"))
        self.assertEqual(rows[0].rrsp_deduction, Decimal("4000.00"))


if __name__ == "__main__":
    unittest.main()
