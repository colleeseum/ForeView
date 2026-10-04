# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""What the running application hands to institution connection factories."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeContext:
    """Database access and configuration for the current runtime."""

    connect: Callable[[], sqlite3.Connection]
    # Raw values from finance.config.json, including non-string entries.
    config: Mapping[str, object]
    # A string setting from the environment, falling back to the config file.
    setting: Callable[[str], str | None]
