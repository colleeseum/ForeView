# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Raised when Questrade rejects an access token."""

from __future__ import annotations


class QuestradeUnauthorized(RuntimeError):
    """Questrade answered HTTP 401; refreshing the authorization may fix it."""
