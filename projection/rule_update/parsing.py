"""Shared exact-decimal parsing helpers for official rule providers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal

from projection.public_rules import TaxBracket

from .errors import RuleSourceFormatError

_MONEY = re.compile(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
_RATE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")
_COLUMNAR_BRACKET_TOKEN = re.compile(
    r"\$\s*[0-9][0-9,]*(?:\.[0-9]+)?|unlimited|[0-9]+(?:\.[0-9]+)?\s*%",
    re.IGNORECASE,
)


def decimal_value(value: str) -> Decimal:
    return Decimal(value.replace(",", "").replace("$", "").replace("%", "").replace(" ", ""))


def rate_value(value: str) -> Decimal:
    return decimal_value(value) / Decimal("100")


def money_values(line: str) -> list[Decimal]:
    return [decimal_value(match.group(1)) for match in _MONEY.finditer(line)]


def percentage_values(line: str) -> list[Decimal]:
    return [rate_value(match.group(1)) for match in _RATE.finditer(line)]


def parse_bracket_section(
    section: str, *, expected_count: int, source_name: str
) -> tuple[TaxBracket, ...]:
    brackets: list[TaxBracket] = []
    for line in section.splitlines():
        rate_matches = list(_RATE.finditer(line))
        if len(rate_matches) != 1:
            continue
        rate_match = rate_matches[0]
        rate = rate_value(rate_match.group(1))
        values = money_values(line[: rate_match.start()])
        lowered = line.casefold()
        if "unlimited" in lowered or (
            "more than" in lowered and "not more" not in lowered and "or less" not in lowered
        ):
            upper_bound = None
        elif values:
            upper_bound = values[-1]
        else:
            continue
        brackets.append(TaxBracket(upper_bound=upper_bound, rate=rate))
        if upper_bound is None:
            break
    if len(brackets) == expected_count and brackets[-1].upper_bound is None:
        return tuple(brackets)
    columnar_brackets = _parse_columnar_brackets(section, expected_count)
    if columnar_brackets is None:
        raise RuleSourceFormatError(
            f"Could not parse {expected_count} complete brackets from {source_name}"
        )
    return columnar_brackets


def parse_variable_bracket_section(section: str, *, source_name: str) -> tuple[TaxBracket, ...]:
    """Parse a complete columnar bracket table without assuming its row count."""
    tokens = [match.group() for match in _COLUMNAR_BRACKET_TOKEN.finditer(section)]
    brackets: list[TaxBracket] = []
    for index in range(0, len(tokens) - 2, 3):
        lower, upper, rate = tokens[index : index + 3]
        if not lower.lstrip().startswith("$") or not rate.rstrip().endswith("%"):
            break
        upper_bound = None if upper.casefold() == "unlimited" else decimal_value(upper)
        brackets.append(TaxBracket(upper_bound=upper_bound, rate=rate_value(rate)))
        if upper_bound is None:
            return tuple(brackets)
    raise RuleSourceFormatError(f"Could not parse a complete bracket table from {source_name}")


def _parse_columnar_brackets(section: str, expected_count: int) -> tuple[TaxBracket, ...] | None:
    tokens = [match.group() for match in _COLUMNAR_BRACKET_TOKEN.finditer(section)]
    required_token_count = expected_count * 3
    if len(tokens) < required_token_count:
        return None
    tokens = tokens[:required_token_count]
    brackets = []
    for index in range(0, len(tokens), 3):
        lower, upper, rate = tokens[index : index + 3]
        if not lower.lstrip().startswith("$") or not rate.rstrip().endswith("%"):
            return None
        upper_bound = None if upper.casefold() == "unlimited" else decimal_value(upper)
        brackets.append(TaxBracket(upper_bound=upper_bound, rate=rate_value(rate)))
    if brackets[-1].upper_bound is not None:
        return None
    return tuple(brackets)


def require_year_row(rows: Sequence[Sequence[str]], year: int, *, source_name: str) -> list[str]:
    for row in rows:
        cells = [cell.strip() for cell in row]
        if cells and cells[0] == str(year):
            return cells
    raise RuleSourceFormatError(f"Could not find {year} in {source_name}")


def year_rows(rows: Sequence[Sequence[str]], year: int) -> list[list[str]]:
    result = []
    for row in rows:
        cells = [cell.strip() for cell in row]
        if cells and cells[0] == str(year):
            result.append(cells)
    return result


def labeled_amount(rows: Sequence[Sequence[str]], label: str, *, source_name: str) -> Decimal:
    for row in rows:
        if row and label.casefold() in row[0].casefold():
            values = money_values(" ".join(row[1:]))
            if values:
                return values[0]
    raise RuleSourceFormatError(f"Could not find {label} in {source_name}")


def labeled_rates(rows: Sequence[Sequence[str]], label: str, *, source_name: str) -> list[Decimal]:
    for row in rows:
        if row and label.casefold() in row[0].casefold():
            rates = percentage_values(" ".join(row[1:]))
            if rates:
                return rates
    raise RuleSourceFormatError(f"Could not find {label} in {source_name}")
