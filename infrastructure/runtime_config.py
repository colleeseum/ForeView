"""One self-contained runtime: its data folder, database, and configuration."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from infrastructure.closing_connection import ClosingConnection
from institution_support.runtime_context import RuntimeContext

CONFIG_FILENAME = "finance.config.json"
DATABASE_FILENAME = "finance.sqlite3"


@dataclass(frozen=True)
class RuntimeConfig:
    """Configuration and database access for one runtime folder."""

    data_dir: Path
    # Non-empty values from finance.config.json; read-only.
    values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_dir", self.data_dir.expanduser().resolve())
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    @classmethod
    def load(cls, data_dir: Path) -> RuntimeConfig:
        """Read a runtime folder's config file without opening its database."""
        config_path = data_dir.expanduser().resolve() / CONFIG_FILENAME
        if not config_path.exists():
            return cls(data_dir)
        try:
            values = json.loads(config_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not read {config_path.name}: {error}") from error
        if not isinstance(values, dict):
            raise RuntimeError(f"{config_path.name} must contain a JSON object")
        return cls(
            data_dir,
            {str(key): value for key, value in values.items() if value not in (None, "")},
        )

    @property
    def config_path(self) -> Path:
        return self.data_dir / CONFIG_FILENAME

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILENAME

    def with_values(self, **changes: object) -> RuntimeConfig:
        """A copy with some config values replaced; a value of None removes the key."""
        values = {**self.values, **changes}
        return RuntimeConfig(
            self.data_dir, {key: value for key, value in values.items() if value is not None}
        )

    def setting(self, name: str, default: str | None = None) -> str | None:
        """A string setting from the environment, falling back to the config file."""
        value = os.environ.get(name)
        if value:
            return value
        configured = self.values.get(name, default)
        return configured if isinstance(configured, str) else default

    def ssl_context(self) -> tuple[str, str] | None:
        cert_file = self.setting("TLS_CERT_FILE")
        key_file = self.setting("TLS_KEY_FILE")
        return (cert_file, key_file) if cert_file and key_file else None

    def connect(self) -> ClosingConnection:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, factory=ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def context(self) -> RuntimeContext:
        """What institution connection factories receive."""
        return RuntimeContext(connect=self.connect, config=self.values, setting=self.setting)
