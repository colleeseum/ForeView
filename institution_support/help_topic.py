# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""User-facing help supplied by an institution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


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
    translations: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
