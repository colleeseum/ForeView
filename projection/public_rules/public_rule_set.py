"""A complete, versioned set of public rules for one jurisdiction and year."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field, HttpUrl, model_validator
from pydantic_core import Url

from .enums import RuleStatus
from .projection_assumption import ProjectionAssumption
from .rule_model import RuleModel
from .rule_parameter import RuleParameter
from .rule_source import RuleSource
from .tax_bracket_schedule import TaxBracketSchedule


class PublicRuleSet(RuleModel):
    schema_version: int = Field(default=1, ge=1)
    rule_set_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    jurisdiction: str = Field(pattern=r"^[A-Z]{2}(?:-[A-Z0-9]{2,3})?$")
    tax_year: int = Field(ge=2000, le=9999)
    status: RuleStatus
    published_on: date | None = None
    effective_from: date
    effective_to: date
    sources: tuple[RuleSource, ...] = Field(min_length=1)
    tax_brackets: tuple[TaxBracketSchedule, ...] = ()
    credits: tuple[RuleParameter, ...] = ()
    payroll_parameters: tuple[RuleParameter, ...] = ()
    contribution_limits: tuple[RuleParameter, ...] = ()
    other_parameters: tuple[RuleParameter, ...] = ()
    based_on_rule_set_id: str | None = None
    projection_assumptions: tuple[ProjectionAssumption, ...] = ()

    @model_validator(mode="after")
    def validate_rule_set(self) -> PublicRuleSet:
        if self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        if self.effective_from.year != self.tax_year or self.effective_to.year != self.tax_year:
            raise ValueError("Effective dates must fall within tax_year")

        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Source IDs must be unique")
        known_sources = set(source_ids)
        rule_items: tuple[TaxBracketSchedule | RuleParameter, ...] = (
            *self.tax_brackets,
            *self.credits,
            *self.payroll_parameters,
            *self.contribution_limits,
            *self.other_parameters,
        )
        referenced_sources = {source_id for item in rule_items for source_id in item.source_ids}
        missing_sources = referenced_sources - known_sources
        if missing_sources:
            raise ValueError(f"Unknown source IDs: {', '.join(sorted(missing_sources))}")

        schedule_codes = [item.code for item in self.tax_brackets]
        if len(schedule_codes) != len(set(schedule_codes)):
            raise ValueError("Tax bracket schedule codes must be unique")
        parameter_codes = [
            item.code
            for item in (
                *self.credits,
                *self.payroll_parameters,
                *self.contribution_limits,
                *self.other_parameters,
            )
        ]
        if len(parameter_codes) != len(set(parameter_codes)):
            raise ValueError("Parameter codes must be unique across the rule set")

        if self.status == RuleStatus.OFFICIAL:
            if self.based_on_rule_set_id is not None or self.projection_assumptions:
                raise ValueError("OFFICIAL rules cannot define projected ancestry or assumptions")
        elif self.based_on_rule_set_id is None or not self.projection_assumptions:
            raise ValueError("PROJECTED rules require a source rule set and projection assumptions")
        if self.based_on_rule_set_id == self.rule_set_id:
            raise ValueError("A projected rule set cannot be based on itself")

        assumption_codes = [item.code for item in self.projection_assumptions]
        if len(assumption_codes) != len(set(assumption_codes)):
            raise ValueError("Projection assumption codes must be unique")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            _canonical_value(self.model_dump(mode="python", exclude_none=False)),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _canonical_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (HttpUrl, Url)):
        return str(value)
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value
