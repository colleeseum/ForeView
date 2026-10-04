# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""How an indexed amount is rounded."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from .decimals import ExactDecimal
from .enums import RoundingMode
from .rule_model import RuleModel


class RoundingMetadata(RuleModel):
    increment: ExactDecimal = Field(gt=Decimal("0"))
    mode: RoundingMode
