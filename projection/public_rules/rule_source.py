# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""An official publication cited by a rule set."""

from __future__ import annotations

from datetime import date

from pydantic import Field, HttpUrl, model_validator

from .rule_model import RuleModel


class RuleSource(RuleModel):
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    url: HttpUrl
    published_on: date | None = None
    accessed_on: date

    @model_validator(mode="after")
    def validate_source_dates(self) -> RuleSource:
        if self.published_on is not None and self.accessed_on < self.published_on:
            raise ValueError("accessed_on cannot precede published_on")
        return self
