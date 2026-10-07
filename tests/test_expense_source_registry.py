# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Tests for expense-source provider discovery and validation."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from domain.parsed_expense_statement import ParsedExpenseStatement
from expense_sources.expense_source_provider import ExpenseSourceProvider
from expense_sources.registry import ExpenseSourceRegistry, expense_source_registry


def _parsed() -> ParsedExpenseStatement:
    return ParsedExpenseStatement(
        suggested_identity="Synthetic utility",
        amount=Decimal("10.00"),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        period_kind="recurring_statement",
    )


def _provider(
    key: str,
    *,
    detects: bool = False,
    version: str = "2026.10.06",
) -> ExpenseSourceProvider:
    return ExpenseSourceProvider(
        key=key,
        display_name=key.title(),
        parser=lambda _content: _parsed(),
        detects=lambda _content: detects,
        help_text="Synthetic provider help.",
        version=version,
    )


class ExpenseSourceRegistryTest(unittest.TestCase):
    def test_discovers_hydro_provider(self) -> None:
        self.assertEqual(expense_source_registry.get("hydro-quebec").key, "hydro-quebec")

    def test_rejects_invalid_calver(self) -> None:
        with self.assertRaisesRegex(ValueError, "must use CalVer"):
            ExpenseSourceRegistry((_provider("invalid", version="1.0.0"),))

    def test_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate expense source"):
            ExpenseSourceRegistry((_provider("same"), _provider("same")))

    def test_unknown_key_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown expense source"):
            ExpenseSourceRegistry(()).get("missing")

    def test_no_detected_source_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match"):
            ExpenseSourceRegistry((_provider("one"),)).detect(b"document")

    def test_ambiguous_detection_raises(self) -> None:
        registry = ExpenseSourceRegistry(
            (_provider("one", detects=True), _provider("two", detects=True))
        )
        with self.assertRaisesRegex(ValueError, "multiple expense sources"):
            registry.detect(b"document")


if __name__ == "__main__":
    unittest.main()
