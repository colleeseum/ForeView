# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from datetime import date

CalendarDateSortKey = tuple[int, date, str, int]
BalanceEventSortKey = tuple[CalendarDateSortKey, int, int]


def parse_calendar_date(value: object) -> date | None:
    """Parse a valid ISO date form without accepting malformed legacy values."""
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def canonical_date_or_stored(value: object) -> str:
    """Canonicalize valid ISO forms while preserving malformed legacy evidence."""
    parsed = parse_calendar_date(value)
    return parsed.isoformat() if parsed is not None else str(value)


def calendar_date_sort_key(value: object, identifier: int) -> CalendarDateSortKey:
    """Order valid ISO forms by date and malformed legacy values deterministically first."""
    parsed = parse_calendar_date(value)
    if parsed is None:
        return 0, date.min, str(value), identifier
    return 1, parsed, "", identifier


def balance_event_sort_key(value: object, identifier: int) -> BalanceEventSortKey:
    """Negative snapshot IDs precede transactions, preserving insertion order within each."""
    return calendar_date_sort_key(value, 0), int(identifier >= 0), abs(identifier)
