"""How a rule value is indexed from one year to the next."""

from __future__ import annotations

from pydantic import Field, model_validator

from .decimals import RateDecimal
from .enums import IndexingMechanism
from .rounding_metadata import RoundingMetadata
from .rule_model import RuleModel


class IndexingMetadata(RuleModel):
    mechanism: IndexingMechanism
    reference_series: str | None = None
    reference_jurisdiction: str | None = None
    lag_years: int = Field(default=0, ge=0)
    fixed_rate: RateDecimal | None = None
    rounding: RoundingMetadata | None = None

    @model_validator(mode="after")
    def validate_mechanism_fields(self) -> IndexingMetadata:
        if self.mechanism == IndexingMechanism.FIXED_RATE and self.fixed_rate is None:
            raise ValueError("FIXED_RATE indexing requires fixed_rate")
        if self.mechanism != IndexingMechanism.FIXED_RATE and self.fixed_rate is not None:
            raise ValueError("fixed_rate is only valid for FIXED_RATE indexing")
        if self.mechanism == IndexingMechanism.NONE and (
            self.reference_series is not None
            or self.reference_jurisdiction is not None
            or self.lag_years
        ):
            raise ValueError("NONE indexing cannot define a reference series, jurisdiction, or lag")
        return self
