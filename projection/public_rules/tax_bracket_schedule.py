# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""An ordered, open-ended set of tax brackets."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, model_validator

from .indexing_metadata import IndexingMetadata
from .rule_model import RuleModel
from .tax_bracket import TaxBracket


class TaxBracketSchedule(RuleModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    brackets: tuple[TaxBracket, ...] = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    threshold_indexing: IndexingMetadata
    rate_indexing: IndexingMetadata
    description: str | None = None

    @model_validator(mode="after")
    def validate_brackets(self) -> TaxBracketSchedule:
        previous: Decimal | None = None
        for index, bracket in enumerate(self.brackets):
            if bracket.upper_bound is None:
                if index != len(self.brackets) - 1:
                    raise ValueError("An open-ended tax bracket must be last")
                continue
            if previous is not None and bracket.upper_bound <= previous:
                raise ValueError("Tax bracket upper bounds must be strictly increasing")
            previous = bracket.upper_bound
        if self.brackets[-1].upper_bound is not None:
            raise ValueError("The final tax bracket must be open-ended")
        return self
