from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Person:
    """A person who can own financial assets."""

    id: int
    name: str
    birth_date: str | None = None
