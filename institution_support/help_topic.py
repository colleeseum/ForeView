# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""User-facing help supplied by an institution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpTopic:
    """User-facing help supplied by an institution provider."""

    key: str
    title: str
    body: str
    category: str = "imports"
    parent_topic: str | None = None
    order: int = 0
    owning_page: str | None = None
