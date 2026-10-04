# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Imported and duplicate row counts for one statement import."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RowCounts:
    imported: int = 0
    duplicates: int = 0

    def __add__(self, other: RowCounts) -> RowCounts:
        return RowCounts(self.imported + other.imported, self.duplicates + other.duplicates)
