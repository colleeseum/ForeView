# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scenario:
    """One immutable projection scenario definition."""

    id: int
    name: str
    baseline_date: str
    description: str | None
