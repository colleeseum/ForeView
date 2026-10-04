# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from flask import current_app


def dependency(name: str) -> Callable[..., Any]:
    """Return an application dependency configured by the composition root."""
    return cast(Callable[..., Any], current_app.extensions[f"finance_{name}"])
