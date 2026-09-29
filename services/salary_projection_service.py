from __future__ import annotations

import sqlite3
from pathlib import Path

from domain.projected_employment_year import ProjectedEmploymentYear
from projection.public_rules import PublicRuleSet
from projection.salary import EmploymentIncomeProjector, QuebecEmploymentTaxCalculator
from repositories.employment_baseline_repository import EmploymentBaselineRepository
from repositories.employment_projection_override_repository import (
    EmploymentProjectionOverrideRepository,
)
from repositories.employment_projection_settings_repository import (
    EmploymentProjectionSettingsRepository,
)
from repositories.person_repository import PersonRepository
from repositories.public_rule_approval_repository import PublicRuleApprovalRepository
from repositories.scenario_repository import ScenarioRepository
from services.public_rule_catalog import PublicRuleCatalog


class SalaryProjectionService:
    """Compose factual inputs, scenario assumptions and approved public rules."""

    def __init__(self, connection: sqlite3.Connection, public_rules_path: Path) -> None:
        self._connection = connection
        self._catalog = PublicRuleCatalog(public_rules_path)

    def project_person(
        self,
        scenario_id: int,
        person_id: int,
        start_year: int,
        end_year: int,
    ) -> tuple[ProjectedEmploymentYear, ...]:
        if ScenarioRepository(self._connection).get(scenario_id) is None:
            raise ValueError("Scenario does not exist")
        person = PersonRepository(self._connection).get(person_id)
        if person is None:
            raise ValueError("Person does not exist")
        baseline = EmploymentBaselineRepository(self._connection).get_effective(
            person_id, f"{start_year}-12-31"
        )
        if baseline is None:
            raise ValueError("Add an employment baseline before projecting this person")
        settings = EmploymentProjectionSettingsRepository(self._connection).get(
            scenario_id, person_id
        )
        if settings is None:
            raise ValueError("Save employment projection settings before projecting this person")
        overrides = tuple(
            EmploymentProjectionOverrideRepository(self._connection).list_for_person(
                scenario_id, person_id
            )
        )
        plans = EmploymentIncomeProjector().project(
            baseline,
            settings,
            overrides,
            start_year=start_year,
            end_year=end_year,
            birth_date=person.birth_date,
        )
        calculator = QuebecEmploymentTaxCalculator()
        rows = []
        for plan in plans:
            federal, federal_held = self._approved_rules("CA", plan.year)
            quebec, quebec_held = self._approved_rules("CA-QC", plan.year)
            payroll_jurisdiction = (
                "CA-QC"
                if baseline.payroll_plan == "QPP"
                else f"CA-{baseline.province_of_employment}"
            )
            payroll, payroll_held = self._approved_rules(payroll_jurisdiction, plan.year)
            estimate = calculator.calculate(
                employment_income=plan.salary_income,
                other_employment_income=plan.other_income,
                rrsp_contribution=plan.rrsp_contribution,
                rrsp_deduction=plan.rrsp_deduction,
                employment_fraction=plan.employment_fraction,
                payroll_plan=baseline.payroll_plan,
                federal_rules=federal,
                quebec_rules=quebec,
                payroll_rules=payroll,
            )
            rows.append(
                ProjectedEmploymentYear(
                    year=plan.year,
                    age=plan.age,
                    annual_salary_rate=plan.annual_salary_rate,
                    raise_rate=plan.raise_rate,
                    employment_fraction=plan.employment_fraction,
                    salary_income=plan.salary_income,
                    other_income=plan.other_income,
                    gross_income=estimate.gross_income,
                    rrsp_contribution=estimate.rrsp_contribution,
                    rrsp_deduction=estimate.rrsp_deduction,
                    cpp_qpp=estimate.payroll.pension_total,
                    ei=estimate.payroll.ei,
                    qpip=estimate.payroll.qpip,
                    federal_tax=estimate.federal_tax,
                    quebec_tax=estimate.quebec_tax,
                    net_income_after_tax=estimate.net_income_after_tax,
                    disposable_income=estimate.disposable_income,
                    rule_year=estimate.rule_year,
                    rules_held_constant=federal_held or quebec_held or payroll_held,
                )
            )
        return tuple(rows)

    def _approved_rules(
        self, jurisdiction: str, projection_year: int
    ) -> tuple[PublicRuleSet, bool]:
        candidates = [
            package
            for package in self._catalog.list_packages()
            if package.rule_set.jurisdiction == jurisdiction
            and package.rule_set.tax_year <= projection_year
        ]
        if not candidates:
            raise ValueError(
                f"No public rules are available for {jurisdiction} in {projection_year}"
            )
        package = max(candidates, key=lambda item: item.rule_set.tax_year)
        approval = PublicRuleApprovalRepository(self._connection).get(
            package.rule_set.rule_set_id, package.content_hash
        )
        if approval is None:
            raise ValueError(
                f"Approve public rules {package.rule_set.rule_set_id} before calculating"
            )
        return package.rule_set, package.rule_set.tax_year != projection_year
