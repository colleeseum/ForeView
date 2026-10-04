# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicPensionStatement:
    """Imported official CPP/QPP participation statement metadata."""

    id: int
    person_id: int
    issued_on: str
    provider: str
    excludes_second_enhancement: bool
    source_version: str
    document_hash: str
