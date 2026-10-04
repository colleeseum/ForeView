# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Find which registered institution importer recognizes a document."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from institution_support.document_importer import DocumentImporter
from institution_support.registry import institution_registry


@dataclass(frozen=True)
class DetectedImporter:
    spec: DocumentImporter
    importer: Callable


def detect_importer(content: bytes, institution: str | None = None) -> DetectedImporter | None:
    for _provider, spec in institution_registry().importers(institution):
        if spec.detects(content):
            return DetectedImporter(spec, spec.importer)
    return None
