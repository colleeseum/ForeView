# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""An immutable interval in an effective marginal tax-rate schedule."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EffectiveMarginalRate:
    upper_bound: Decimal | None
    rate: Decimal
