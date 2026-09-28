"""Base model for immutable, strictly validated public-rule data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RuleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
