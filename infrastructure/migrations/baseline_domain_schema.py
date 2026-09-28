from __future__ import annotations

import sqlite3
from collections.abc import Callable

from infrastructure.domain_schema import DomainSchemaManager


class BaselineDomainSchemaMigration:
    """Capture the schema and compatibility work that predates migration tracking."""

    version = 1
    name = "baseline_domain_schema"

    def __init__(self, migrate_fixed_deposits: Callable[[], int]) -> None:
        self._migrate_fixed_deposits = migrate_fixed_deposits

    def apply(self, connection: sqlite3.Connection) -> None:
        DomainSchemaManager(
            connection,
            migrate_fixed_deposits=self._migrate_fixed_deposits,
        ).ensure()
