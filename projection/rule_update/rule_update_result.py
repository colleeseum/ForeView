"""Outcome of generating one reviewable public-rule package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuleUpdateResult:
    provider_id: str
    jurisdiction: str
    tax_year: int
    package_directory: Path
    rule_set_hashes: tuple[str, ...]
    source_hashes: tuple[str, ...]
