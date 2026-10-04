# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""One official source document fetched for a public-rule update."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RetrievedSource:
    source_id: str
    title: str
    publisher: str
    url: str
    content_type: str
    content: bytes
    retrieved_at: datetime

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content).hexdigest()
