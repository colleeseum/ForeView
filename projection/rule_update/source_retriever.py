# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Fetches official source documents for public-rule providers."""

from __future__ import annotations

from typing import Protocol

from .retrieved_source import RetrievedSource


class SourceRetriever(Protocol):
    def retrieve(
        self,
        *,
        source_id: str,
        title: str,
        publisher: str,
        url: str,
        user_agent: str | None = None,
    ) -> RetrievedSource: ...
