# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuestradeAuthorization:
    """Stored OAuth tokens for one named Questrade login; tokens are encrypted."""

    id: int
    name: str
    access_token: str
    refresh_token: str
    api_server: str
    access_expires_at: str | None
    refresh_expires_at: str | None
    last_sync_attempt_at: str | None
    last_sync_at: str | None
    last_sync_error: str | None
    updated_at: str | None

    def status(self) -> dict[str, object]:
        """Connection state safe to show the user, without token values."""
        return {
            "id": self.id,
            "name": self.name,
            "updated_at": self.updated_at,
            "api_server": self.api_server,
            "access_expires_at": self.access_expires_at,
            "last_sync_attempt_at": self.last_sync_attempt_at,
            "last_sync_at": self.last_sync_at,
            "last_sync_error": self.last_sync_error,
        }
