# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from infrastructure.migrations.factual_expenses import FactualExpensesMigration
from repositories.expense_repository import ExpenseRepository


def repository() -> ExpenseRepository:
    connection = sqlite3.connect(":memory:")
    FactualExpensesMigration().apply(connection)
    return ExpenseRepository(connection)


def test_categories_are_user_defined_and_can_be_archived() -> None:
    repo = repository()
    utilities = repo.create_category("Utilities", "required")
    travel = repo.create_category("Travel", "discretionary")

    assert [category.name for category in repo.list_categories()] == ["Travel", "Utilities"]
    repo.rename_category(utilities.id, "House utilities")
    repo.set_category_active(travel.id, False)

    assert [category.name for category in repo.list_categories()] == ["House utilities"]
    assert {category.name for category in repo.list_categories(include_inactive=True)} == {
        "House utilities", "Travel"
    }


def test_manual_expense_preserves_period_category_and_household_scope() -> None:
    repo = repository()
    category = repo.create_category("Travel", "discretionary")

    expense = repo.create_manual_expense(
        name="Italy Trip",
        category_id=category.id,
        amount="6500.00",
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
    )

    assert expense.name == "Italy Trip"
    assert expense.amount == 6500
    assert expense.source_kind == "manual"
    assert expense.association_kind == "household"


def test_year_summary_preserves_categories_and_classification() -> None:
    repo = repository()
    utilities = repo.create_category("Utilities", "required")
    travel = repo.create_category("Travel", "discretionary")
    repo.create_manual_expense(
        name="Hydro", category_id=utilities.id, amount="3842.17",
        period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
    )
    repo.create_manual_expense(
        name="Italy Trip", category_id=travel.id, amount="6500",
        period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
    )

    summary = repo.totals_for_year(2026)
    assert summary["required"] == 3842.17
    assert summary["discretionary"] == 6500
    assert summary["total"] == 10342.17


def test_person_or_asset_association_requires_an_id() -> None:
    repo = repository()
    category = repo.create_category("Tuition", "required")

    with pytest.raises(ValueError, match="require an association id"):
        repo.create_manual_expense(
            name="University", category_id=category.id, amount=1000,
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            association_kind="person",
        )
