# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3

from domain.scenario import Scenario
from repositories.employment_projection_override_repository import (
    EmploymentProjectionOverrideRepository,
)
from repositories.employment_projection_settings_repository import (
    EmploymentProjectionSettingsRepository,
)
from repositories.household_expense_plan_repository import HouseholdExpensePlanRepository
from repositories.person_repository import PersonRepository
from repositories.real_estate_projection_repository import RealEstateProjectionRepository
from repositories.scenario_assumption_repository import ScenarioAssumptionRepository
from repositories.scenario_repository import ScenarioRepository


class ScenarioCloneService:
    """Clone a scenario and every scenario-owned projection value."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def clone(self, source_scenario_id: int, name: str) -> Scenario:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Scenario name is required")

        scenarios = ScenarioRepository(self._connection)
        source = scenarios.get(source_scenario_id)
        if source is None:
            raise ValueError("Source scenario does not exist")
        clone = scenarios.create(clean_name, source.baseline_date, source.description)

        assumptions = ScenarioAssumptionRepository(self._connection)
        for assumption in assumptions.list_for_scenario(source.id):
            assumptions.set(clone.id, assumption.key, assumption.value, assumption.unit)

        settings_repository = EmploymentProjectionSettingsRepository(self._connection)
        for settings in settings_repository.list_for_scenario(source.id):
            settings_repository.upsert(
                clone.id,
                settings.person_id,
                default_raise=settings.default_raise,
                retirement_date=settings.retirement_date,
                recurring_rrsp_contribution=settings.recurring_rrsp_contribution,
                recurring_rrsp_deduction=settings.recurring_rrsp_deduction,
                recurring_other_income=settings.recurring_other_income,
            )

        overrides = EmploymentProjectionOverrideRepository(self._connection)
        for person in PersonRepository(self._connection).list_all():
            for override in overrides.list_for_person(source.id, person.id):
                overrides.upsert(
                    clone.id,
                    person.id,
                    override.projection_year,
                    salary=override.salary,
                    raise_rate=override.raise_rate,
                    rrsp_contribution=override.rrsp_contribution,
                    rrsp_deduction=override.rrsp_deduction,
                    other_income=override.other_income,
                )

        real_estate = RealEstateProjectionRepository(self._connection)
        for projection in real_estate.list_for_scenario(source.id):
            real_estate.create(
                projection.asset_id,
                projection.projection_date,
                projection.projected_value,
                scenario_id=clone.id,
                projected_acb=projection.projected_acb,
                effective_tax_rate=projection.effective_tax_rate,
                note=projection.note,
            )
        expenses = HouseholdExpensePlanRepository(self._connection).get(source.id)
        if expenses is not None:
            HouseholdExpensePlanRepository(self._connection).upsert(
                clone.id,
                start_year=expenses.start_year,
                required_annual_amount=expenses.required_annual_amount,
                required_annual_growth=expenses.required_annual_growth,
                discretionary_annual_amount=expenses.discretionary_annual_amount,
                discretionary_annual_growth=expenses.discretionary_annual_growth,
            )
        return clone
