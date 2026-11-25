# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ImportSource:
    """Request-local original bytes and filename, never a path to open or retain."""

    filename: str = field(repr=False)
    content: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.filename, str) or not self.filename.strip():
            raise ValueError("Source filename must be non-empty text")
        if not isinstance(self.content, bytes):
            raise TypeError("Source content must be immutable bytes")

    @property
    def content_hash(self) -> str:
        """Hash only the original bytes; filename remains a separate parsing input."""
        return hashlib.sha256(self.content).hexdigest()
