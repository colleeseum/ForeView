"""An assumption used to project a future year's rules."""

from __future__ import annotations

from pydantic import Field

from .decimals import ExactDecimal
from .enums import RuleUnit
from .rule_model import RuleModel


class ProjectionAssumption(RuleModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    value: ExactDecimal
    unit: RuleUnit
    description: str | None = None
