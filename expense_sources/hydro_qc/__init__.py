# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Hydro-Québec factual-expense source provider."""

from pathlib import Path

from expense_sources.expense_source_provider import ExpenseSourceProvider
from expense_sources.hydro_qc.parser import HydroQuebecParser


def provider() -> ExpenseSourceProvider:
    parser = HydroQuebecParser()
    return ExpenseSourceProvider(
        key="hydro-quebec",
        display_name="Hydro-Québec electricity bill",
        parser=parser.parse,
        detects=parser.detects,
        help_text=(Path(__file__).parent / "HELP.md").read_text(encoding="utf-8"),
        version=parser.VERSION,
    )


__all__ = ["HydroQuebecParser", "provider"]
