"""Translates official sources into public-rule sets for one jurisdiction."""

from __future__ import annotations

from typing import Protocol

from projection.public_rules import PublicRuleSet

from .source_retriever import SourceRetriever


class PublicRuleProvider(Protocol):
    provider_id: str
    jurisdiction: str

    def fetch(self, tax_year: int, retriever: SourceRetriever) -> tuple[PublicRuleSet, ...]: ...
