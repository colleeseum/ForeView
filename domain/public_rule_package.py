"""Immutable view of a version-controlled public-rule package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projection.public_rules import PublicRuleSet


@dataclass(frozen=True, slots=True)
class PublicRulePackage:
    rule_set: PublicRuleSet
    content_hash: str
    manifest_path: Path
    source_files: tuple[Path, ...]
