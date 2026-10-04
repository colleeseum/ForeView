# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from pydantic import HttpUrl

from projection.public_rules import RuleSource

from .retrieved_source import RetrievedSource


def rule_source(source: RetrievedSource) -> RuleSource:
    return RuleSource(
        source_id=source.source_id,
        title=source.title,
        publisher=source.publisher,
        url=HttpUrl(source.url),
        accessed_on=source.retrieved_at.date(),
    )
