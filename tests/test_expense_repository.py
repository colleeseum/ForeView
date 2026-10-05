# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from infrastructure.migrations.expense_identities import ExpenseIdentitiesMigration
from infrastructure.migrations.expense_period_kind import ExpensePeriodKindMigration
from infrastructure.migrations.factual_expenses import FactualExpensesMigration
from repositories.expense_repository import ExpenseRepository


@pytest.fixture
def repo() -> ExpenseRepository:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("CREATE TABLE people(id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    connection.execute("CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT)")
    connection.execute(
        "CREATE TABLE real_estate_assets(id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE import_batches(id INTEGER PRIMARY KEY, filename TEXT NOT NULL, file_hash TEXT NOT NULL UNIQUE)"
    )
    FactualExpensesMigration().apply(connection)
    ExpenseIdentitiesMigration().apply(connection)
    ExpensePeriodKindMigration().apply(connection)
    repository = ExpenseRepository(connection)
    try:
        yield repository
    finally:
        connection.close()


def test_categories_are_user_defined_and_can_be_archived(repo: ExpenseRepository) -> None:
    utilities = repo.create_category("Utilities", "required")
    travel = repo.create_category("Travel", "discretionary")
    assert [category.name for category in repo.list_categories()] == ["Travel", "Utilities"]
    repo.rename_category(utilities.id, "House utilities")
    repo.set_category_active(travel.id, False)
    assert [category.name for category in repo.list_categories()] == ["House utilities"]


def test_manual_expense_preserves_period_category_and_household_scope(
    repo: ExpenseRepository,
) -> None:
    category = repo.create_category("Travel", "discretionary")
    expense = repo.create_manual_expense(
        name="Italy Trip",
        category_id=category.id,
        amount="6500.00",
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
    )
    assert expense.amount == Decimal("6500.00")
    assert expense.classification == "discretionary"
    assert expense.source_kind == "manual"


def test_year_summary_uses_decimal_and_historical_classification(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="3842.17",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    repo.reclassify_category(category.id, "discretionary")
    summary = repo.totals_for_year(2026)
    assert summary["required"] == Decimal("3842.17")
    assert summary["discretionary"] == Decimal("0.00")
    assert summary["total"] == Decimal("3842.17")


def test_missing_year_is_not_reported_as_zero(repo: ExpenseRepository) -> None:
    summary = repo.totals_for_year(2026)
    assert summary["status"] == "missing"
    assert summary["required"] is None
    assert summary["discretionary"] is None
    assert summary["total"] is None


def test_multi_year_record_is_prorated_by_days(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    repo.create_manual_expense(
        name="Billing period",
        category_id=category.id,
        amount="1200.00",
        period_start=date(2025, 12, 1),
        period_end=date(2026, 1, 31),
    )
    assert repo.totals_for_year(2025)["total"] == Decimal("600.00")
    assert repo.totals_for_year(2026)["total"] == Decimal("600.00")


def test_archived_category_rejects_new_records(repo: ExpenseRepository) -> None:
    category = repo.create_category("Old", "required")
    repo.set_category_active(category.id, False)
    with pytest.raises(ValueError, match="archived"):
        repo.create_manual_expense(
            name="No",
            category_id=category.id,
            amount=1,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 1),
        )


def test_person_and_asset_associations_must_exist(repo: ExpenseRepository) -> None:
    category = repo.create_category("Tuition", "required")
    with pytest.raises(ValueError, match="Unknown person"):
        repo.create_manual_expense(
            name="University",
            category_id=category.id,
            amount=1000,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            association_kind="person",
            association_id=99,
        )


def test_imported_expense_has_public_provenance_api(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    repo._connection.execute(
        "INSERT INTO import_batches(id, filename, file_hash) VALUES (1, 'statement.pdf', 'abc')"
    )
    expense = repo.create_imported_expense(
        name="Hydro",
        category_id=category.id,
        amount="100.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        source_document_id=1,
        parser_name="hydro",
        period_kind="recurring_statement",
        parser_version="1",
    )
    assert expense.source_kind == "imported"
    assert expense.source_document_id == 1
    assert expense.source_name == "statement.pdf"
    assert expense.source_hash == "abc"
    assert expense.parser_name == "hydro"


def test_imported_expense_requires_an_existing_import_batch(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    with pytest.raises(LookupError, match="Import batch 99"):
        repo.create_imported_expense(
            name="Hydro",
            category_id=category.id,
            amount="100.00",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            source_document_id=99,
            parser_name="hydro",
            period_kind="recurring_statement",
        )


def test_overlap_is_flagged_and_excluded_until_resolved(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    first = repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="100.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    second = repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="100.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    assert repo.get_expense(first.id).overlap_status == "potential"
    assert second.overlap_status == "potential"
    unresolved = repo.totals_for_year(2026)
    assert unresolved["status"] == "needs_resolution"
    assert unresolved["total"] is None
    repo.resolve_overlap(first.id, include=True, note="supported statement")
    repo.resolve_overlap(second.id, include=False, note="duplicate")
    resolved = repo.totals_for_year(2026)
    assert resolved["status"] == "recorded"
    assert resolved["total"] == Decimal("100.00")


def test_different_utilities_can_cover_the_same_period_without_overlap(
    repo: ExpenseRepository,
) -> None:
    category = repo.create_category("Utilities", "required")
    hydro = repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="100.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    gas = repo.create_manual_expense(
        name="Energir",
        category_id=category.id,
        amount="80.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )

    assert hydro.identity_id != gas.identity_id
    assert hydro.overlap_status == "clear"
    assert gas.overlap_status == "clear"
    assert repo.totals_for_year(2026)["total"] == Decimal("180.00")


def test_irregular_period_retains_factual_amount_and_estimates_full_year(
    repo: ExpenseRepository,
) -> None:
    category = repo.create_category("Utilities", "required")
    repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="31.00",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        period_kind="recurring_statement",
    )

    summary = repo.totals_for_year(2025)

    assert summary["total"] == Decimal("31.00")
    assert summary["estimated_total"] == Decimal("365.00")
    assert summary["categories"][0]["amount"] == Decimal("31.00")
    assert summary["categories"][0]["annualized_estimate"] == Decimal("365.00")
    assert summary["has_partial_coverage"] is True


def test_annualized_totals_preserve_historical_category_snapshots(
    repo: ExpenseRepository,
) -> None:
    category = repo.create_category("Utilities", "required")
    repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="31.00",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        period_kind="recurring_statement",
    )
    repo.rename_category(category.id, "Home utilities")
    repo.reclassify_category(category.id, "discretionary")
    repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="28.00",
        period_start=date(2025, 2, 1),
        period_end=date(2025, 2, 28),
        period_kind="recurring_statement",
    )

    summary = repo.totals_for_year(2025)

    categories = {item["name"]: item for item in summary["categories"]}
    assert categories["Utilities"]["classification"] == "required"
    assert categories["Utilities"]["amount"] == Decimal("31.00")
    assert categories["Utilities"]["annualized_estimate"] == Decimal("365.00")
    assert categories["Home utilities"]["classification"] == "discretionary"
    assert categories["Home utilities"]["amount"] == Decimal("28.00")
    assert categories["Home utilities"]["annualized_estimate"] == Decimal("365.00")
    assert summary["estimated_required"] == Decimal("365.00")
    assert summary["estimated_discretionary"] == Decimal("365.00")


def test_edit_clears_orphaned_resolved_overlap_statuses(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    first = repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="100.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    second = repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="80.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    repo.resolve_overlap(first.id, include=True, note="Supported statement")
    repo.resolve_overlap(second.id, include=False, note="Duplicate statement")

    repo.update_expense(
        first.id,
        name="Hydro",
        category_id=category.id,
        amount="100.00",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
    )

    updated_first = repo.get_expense(first.id)
    updated_second = repo.get_expense(second.id)
    assert updated_first.overlap_status == "clear"
    assert updated_first.overlap_resolution_note is None
    assert updated_second.overlap_status == "clear"
    assert updated_second.overlap_resolution_note is None
    assert repo.totals_for_year(2026)["total"] == Decimal("180.00")


def test_year_9999_recurring_expense_can_be_annualized(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    repo.create_manual_expense(
        name="Hydro",
        category_id=category.id,
        amount="31.00",
        period_start=date(9999, 1, 1),
        period_end=date(9999, 1, 31),
        period_kind="recurring_statement",
    )

    summary = repo.totals_for_year(9999)

    assert summary["status"] == "recorded"
    assert summary["total"] == Decimal("31.00")
    assert summary["estimated_total"] == Decimal("365.00")


def test_full_year_evidence_does_not_report_partial_coverage(repo: ExpenseRepository) -> None:
    category = repo.create_category("Property tax", "required")
    repo.create_manual_expense(
        name="Montreal property tax",
        category_id=category.id,
        amount="4200.00",
        period_start=date(2024, 6, 1),
        period_end=date(2024, 6, 1),
    )

    summary = repo.totals_for_year(2024)

    assert summary["estimated_total"] == Decimal("4200.00")
    assert summary["has_partial_coverage"] is False


def test_account_and_real_estate_associations_are_unambiguous(repo: ExpenseRepository) -> None:
    repo._connection.execute("INSERT INTO accounts(id, name) VALUES (1, 'Savings')")
    repo._connection.execute("INSERT INTO real_estate_assets(id, name) VALUES (1, 'House')")
    category = repo.create_category("Property", "required")

    account_expense = repo.create_manual_expense(
        name="Account fee",
        category_id=category.id,
        amount="10.00",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 1),
        association_kind="account",
        association_id=1,
    )
    property_expense = repo.create_manual_expense(
        name="Property tax",
        category_id=category.id,
        amount="100.00",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 1),
        association_kind="real_estate",
        association_id=1,
    )

    assert account_expense.association_kind == "account"
    assert property_expense.association_kind == "real_estate"


def test_cross_year_allocation_preserves_every_cent(repo: ExpenseRepository) -> None:
    category = repo.create_category("Utilities", "required")
    repo.create_manual_expense(
        name="One cent",
        category_id=category.id,
        amount="0.01",
        period_start=date(2025, 12, 31),
        period_end=date(2026, 1, 1),
    )

    allocated = repo.totals_for_year(2025)["total"] + repo.totals_for_year(2026)["total"]

    assert allocated == Decimal("0.01")
