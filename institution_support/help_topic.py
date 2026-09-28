"""User-facing help supplied by an institution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpTopic:
    """User-facing help supplied by an institution provider."""

    key: str
    title: str
    body: str
