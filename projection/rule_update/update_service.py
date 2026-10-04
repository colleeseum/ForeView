# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Generate reviewable public-rule packages from official internet sources."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .provider_registry import PublicRuleProviderRegistry
from .retrieved_source import RetrievedSource
from .rule_update_result import RuleUpdateResult
from .source_retriever import SourceRetriever


class _RecordingRetriever:
    def __init__(self, wrapped: SourceRetriever) -> None:
        self._wrapped = wrapped
        self.sources: list[RetrievedSource] = []

    def retrieve(
        self,
        *,
        source_id: str,
        title: str,
        publisher: str,
        url: str,
        user_agent: str | None = None,
    ) -> RetrievedSource:
        source = self._wrapped.retrieve(
            source_id=source_id,
            title=title,
            publisher=publisher,
            url=url,
            user_agent=user_agent,
        )
        self.sources.append(source)
        return source


class PublicRuleUpdateService:
    def __init__(
        self,
        registry: PublicRuleProviderRegistry,
        retriever: SourceRetriever,
    ) -> None:
        self._registry = registry
        self._retriever = retriever

    def update(
        self, tax_year: int, provider_ids: list[str], output_directory: Path
    ) -> tuple[RuleUpdateResult, ...]:
        if not 2000 <= tax_year <= 9999:
            raise ValueError("tax_year must be between 2000 and 9999")
        results = []
        for provider_id in provider_ids:
            provider = self._registry.get(provider_id)
            recording = _RecordingRetriever(self._retriever)
            rule_sets = provider.fetch(tax_year, recording)
            if not rule_sets:
                raise ValueError(f"Provider returned no rule sets: {provider_id}")
            for rule_set in rule_sets:
                if rule_set.tax_year != tax_year or rule_set.jurisdiction != provider.jurisdiction:
                    raise ValueError(f"Provider returned a mismatched rule set: {provider_id}")
            target = output_directory / str(tax_year) / provider.jurisdiction.lower()
            sources_directory = target / "sources"
            sources_directory.mkdir(parents=True, exist_ok=True)
            source_files = []
            for source in recording.sources:
                extension = self._extension(source.content_type)
                filename = f"{source.source_id}{extension}"
                self._write_bytes(sources_directory / filename, source.content)
                source_files.append(
                    {
                        "source_id": source.source_id,
                        "url": source.url,
                        "content_type": source.content_type,
                        "retrieved_at": source.retrieved_at.isoformat(),
                        "sha256": source.content_hash,
                        "filename": f"sources/{filename}",
                    }
                )
            rule_files = []
            for rule_set in rule_sets:
                filename = f"{rule_set.rule_set_id}.json"
                self._write_text(target / filename, rule_set.canonical_json() + "\n")
                rule_files.append(
                    {
                        "rule_set_id": rule_set.rule_set_id,
                        "sha256": rule_set.content_hash(),
                        "filename": filename,
                    }
                )
            manifest = {
                "provider_id": provider.provider_id,
                "jurisdiction": provider.jurisdiction,
                "tax_year": tax_year,
                "rule_sets": rule_files,
                "sources": source_files,
            }
            self._write_text(
                target / "manifest.json",
                json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
            )
            results.append(
                RuleUpdateResult(
                    provider_id=provider.provider_id,
                    jurisdiction=provider.jurisdiction,
                    tax_year=tax_year,
                    package_directory=target,
                    rule_set_hashes=tuple(item["sha256"] for item in rule_files),
                    source_hashes=tuple(item["sha256"] for item in source_files),
                )
            )
        return tuple(results)

    @staticmethod
    def _extension(content_type: str) -> str:
        return {
            "text/html": ".html",
            "application/xhtml+xml": ".html",
            "application/json": ".json",
            "text/csv": ".csv",
            "text/plain": ".txt",
            "application/pdf": ".pdf",
        }.get(content_type, ".bin")

    @staticmethod
    def _write_text(path: Path, value: str) -> None:
        PublicRuleUpdateService._write_bytes(path, value.encode("utf-8"))

    @staticmethod
    def _write_bytes(path: Path, value: bytes) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", path.name):
            raise ValueError(f"Unsafe public-rule filename: {path.name}")
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(value)
        temporary.replace(path)
