# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.parsed_tax_value import ParsedTaxValue


@dataclass(frozen=True, slots=True)
class ParsedTaxAssessment:
    """Values extracted from one federal or provincial assessment notice."""

    tax_year: int
    jurisdiction: str
    issued_on: str
    taxpayer_name: str | None
    total_income: Decimal
    net_income: Decimal
    taxable_income: Decimal
    net_tax: Decimal
    additional_contributions: Decimal
    tax_withheld: Decimal
    balance: Decimal
    rrsp_effective_year: int | None = None
    rrsp_deduction_limit: Decimal | None = None
    rrsp_unused_deduction_room: Decimal | None = None
    rrsp_new_room: Decimal | None = None
    rrsp_unused_contributions: Decimal | None = None
    rrsp_available_room: Decimal | None = None
    tax_values: tuple[ParsedTaxValue, ...] = ()
