"""One sourced numeric rule value, such as a credit or contribution limit."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, model_validator

from .decimals import ExactDecimal
from .enums import RuleUnit
from .indexing_metadata import IndexingMetadata
from .rule_model import RuleModel


class RuleParameter(RuleModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    value: ExactDecimal
    unit: RuleUnit
    source_ids: tuple[str, ...] = Field(min_length=1)
    indexing: IndexingMetadata
    description: str | None = None

    @model_validator(mode="after")
    def validate_value_for_unit(self) -> RuleParameter:
        if self.unit in {RuleUnit.CAD, RuleUnit.COUNT, RuleUnit.YEARS} and self.value < 0:
            raise ValueError(f"{self.unit.value} values cannot be negative")
        if self.unit == RuleUnit.RATE and not Decimal("0") <= self.value <= Decimal("1"):
            raise ValueError("RATE values must be between 0 and 1")
        return self
