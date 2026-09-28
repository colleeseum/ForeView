"""Immutable local approval of one exact public-rule revision."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicRuleApproval:
    rule_set_id: str
    content_hash: str
    approved_at: str
