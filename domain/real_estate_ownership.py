# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RealEstateOwnership:
    """One person's immutable ownership share in a real-estate asset."""

    asset_id: int
    person_id: int
    share: float
