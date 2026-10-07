# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Load invented factual expenses into an explicitly synthetic runtime."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path

from domain.expense import ExpenseClassification, ExpensePeriodKind
from infrastructure.runtime_config import RuntimeConfig
from repositories.expense_repository import ExpenseRepository
from services.database_initialization import initialize_database


def seed_synthetic_expenses(connection: sqlite3.Connection) -> int:
    """Add deterministic expense fixtures, returning the number of records created."""
    repository = ExpenseRepository(connection)
    categories = {
        category.name.casefold(): category
        for category in repository.list_categories(include_inactive=True)
    }
    category_fixtures: tuple[tuple[str, ExpenseClassification], ...] = (
        ("Utilities", "required"),
        ("Property tax", "required"),
    )
    for name, classification in category_fixtures:
        existing = categories.get(name.casefold())
        if existing is None:
            existing = repository.create_category(name, classification)
            categories[name.casefold()] = existing
        elif existing.classification != classification:
            raise RuntimeError(
                f"Synthetic expense category {name!r} has classification "
                f"{existing.classification!r}, not {classification!r}"
            )
        elif not existing.is_active:
            existing = repository.set_category_active(existing.id, True)
            categories[name.casefold()] = existing

    existing_records = {
        (
            record.name,
            record.category_id,
            str(record.amount),
            record.period_start,
            record.period_end,
            record.period_kind,
        )
        for record in repository.list_expenses()
    }
    fixtures: tuple[tuple[str, int, str, date, date, ExpensePeriodKind], ...] = (
        (
            "Hydro",
            categories["utilities"].id,
            "360.00",
            date(2025, 1, 1),
            date(2025, 6, 30),
            "recurring_statement",
        ),
        (
            "Hydro",
            categories["utilities"].id,
            "640.00",
            date(2025, 7, 1),
            date(2025, 12, 31),
            "recurring_statement",
        ),
        (
            "Energir",
            categories["utilities"].id,
            "720.00",
            date(2025, 1, 1),
            date(2025, 6, 30),
            "recurring_statement",
        ),
        (
            "Energir",
            categories["utilities"].id,
            "1280.00",
            date(2025, 7, 1),
            date(2025, 12, 31),
            "recurring_statement",
        ),
        (
            "Hydro",
            categories["utilities"].id,
            "31.00",
            date(2026, 1, 1),
            date(2026, 1, 31),
            "recurring_statement",
        ),
        (
            "Energir",
            categories["utilities"].id,
            "62.00",
            date(2026, 1, 1),
            date(2026, 1, 31),
            "recurring_statement",
        ),
        (
            "Montreal property tax",
            categories["property tax"].id,
            "4200.00",
            date(2026, 6, 1),
            date(2026, 6, 1),
            "annual_or_one_time",
        ),
    )
    created = 0
    for name, category_id, amount, period_start, period_end, period_kind in fixtures:
        key = (
            name,
            category_id,
            amount,
            period_start.isoformat(),
            period_end.isoformat(),
            period_kind,
        )
        if key in existing_records:
            continue
        repository.create_manual_expense(
            name=name,
            category_id=category_id,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            period_kind=period_kind,
        )
        existing_records.add(key)
        created += 1
    return created


def load_synthetic_expenses(data_dir: Path) -> int:
    """Load fixtures only when the runtime explicitly identifies itself as synthetic."""
    target = data_dir.expanduser().resolve()
    config = json.loads((target / "finance.config.json").read_text())
    if config.get("RUNTIME_ENVIRONMENT") != "synthetic":
        raise RuntimeError("Refusing to load synthetic expenses into a non-synthetic runtime")

    runtime = RuntimeConfig.load(target)
    initialize_database(runtime.connect)
    with runtime.connect() as connection:
        with connection:
            return seed_synthetic_expenses(connection)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(description="Load invented factual expenses")
    argument_parser.add_argument("data_dir", type=Path)
    args = argument_parser.parse_args()
    created_count = load_synthetic_expenses(args.data_dir)
    print(f"Created {created_count} synthetic expense records")
