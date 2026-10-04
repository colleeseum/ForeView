# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""One bracket of a progressive tax schedule."""

from __future__ import annotations

from .decimals import NonNegativeDecimal, RateDecimal
from .rule_model import RuleModel


class TaxBracket(RuleModel):
    upper_bound: NonNegativeDecimal | None
    rate: RateDecimal
