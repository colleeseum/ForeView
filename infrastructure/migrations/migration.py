from __future__ import annotations

import sqlite3
from typing import Protocol


class Migration(Protocol):
    """One append-only database schema transition."""

    version: int
    name: str

    def apply(self, connection: sqlite3.Connection) -> None: ...
