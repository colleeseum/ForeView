"""Raised when Questrade rejects an access token."""

from __future__ import annotations


class QuestradeUnauthorized(RuntimeError):
    """Questrade answered HTTP 401; refreshing the authorization may fix it."""
