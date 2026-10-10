# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date


def payload_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def payload_iso_date(value: object) -> str:
    """Validate and normalize a required Gregorian date-only value."""
    return date.fromisoformat(str(value)).isoformat()
