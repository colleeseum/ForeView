# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Base model for immutable, strictly validated public-rule data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RuleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
