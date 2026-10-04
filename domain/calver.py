"""Calendar-version validation shared by registered modules."""

from __future__ import annotations

import re
from datetime import date

_CALVER = re.compile(r"(?P<year>\d{4})\.(?P<month>\d{2})\.(?P<day>\d{2})(?:\.(?:0|[1-9]\d*))?")


def is_calver(value: str) -> bool:
    """Return whether a value uses YYYY.MM.DD with an optional numeric revision."""
    match = _CALVER.fullmatch(value)
    if not match:
        return False
    try:
        date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return False
    return True
