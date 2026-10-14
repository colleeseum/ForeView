# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from collections.abc import Mapping
from datetime import date
from typing import Any

from domain.validation_error import ValidationError


def payload_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def payload_iso_date(value: object) -> str:
    """Validate and normalize a required Gregorian date-only value."""
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as error:
        raise ValidationError("input_invalid_date", str(error), detail0=str(value)) from error


def required_field(payload: Mapping[str, Any], field: str) -> Any:
    try:
        return payload[field]
    except KeyError as error:
        raise ValidationError("input_required_field", str(error), field=field) from error


def payload_integer(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError) as error:
        raise ValidationError("input_invalid_integer", str(error), value=str(value)) from error


def payload_ratio(value: Any) -> float:
    try:
        return float(value)
    except (ValueError, TypeError) as error:
        raise ValidationError("input_invalid_number", str(error), value=str(value)) from error
