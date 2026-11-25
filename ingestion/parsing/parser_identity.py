# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParserIdentity:
    """Stable format key and explicit interpretation version, not a UI label."""

    key: str
    version: str

    def __post_init__(self) -> None:
        for value in (self.key, self.version):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Parser key and version must be non-empty text")
