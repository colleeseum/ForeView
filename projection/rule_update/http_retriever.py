"""Bounded HTTPS retrieval for official public-rule publications."""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import UTC, datetime
from urllib.parse import urlparse

from .errors import RuleRetrievalError
from .retrieved_source import RetrievedSource


class HttpSourceRetriever:
    def __init__(self, *, timeout_seconds: float = 30, maximum_bytes: int = 8_000_000) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if maximum_bytes <= 0:
            raise ValueError("maximum_bytes must be positive")
        self._timeout_seconds = timeout_seconds
        self._maximum_bytes = maximum_bytes
        self._cache: dict[tuple[str, str | None], tuple[str, str, bytes, datetime]] = {}

    def retrieve(
        self,
        *,
        source_id: str,
        title: str,
        publisher: str,
        url: str,
        user_agent: str | None = None,
    ) -> RetrievedSource:
        self._validate_https(url)
        cache_key = (url, user_agent)
        cached = self._cache.get(cache_key)
        if cached is not None:
            final_url, content_type, content, retrieved_at = cached
            return RetrievedSource(
                source_id=source_id,
                title=title,
                publisher=publisher,
                url=final_url,
                content_type=content_type,
                content=content,
                retrieved_at=retrieved_at,
            )
        headers = {"Accept": "text/html,application/xhtml+xml,application/json,text/plain"}
        if user_agent is not None:
            headers["User-Agent"] = user_agent
        request = urllib.request.Request(
            url,
            headers=headers,
        )
        try:
            # The requested and final redirect schemes are both constrained to HTTPS.
            with urllib.request.urlopen(  # nosec B310
                request, timeout=self._timeout_seconds
            ) as response:
                final_url = response.geturl()
                self._validate_https(final_url)
                content = response.read(self._maximum_bytes + 1)
                if len(content) > self._maximum_bytes:
                    raise RuleRetrievalError(
                        f"{source_id} exceeded the {self._maximum_bytes}-byte safety limit"
                    )
                content_type = response.headers.get_content_type()
        except RuleRetrievalError:
            raise
        except (OSError, urllib.error.URLError) as error:
            raise RuleRetrievalError(f"Could not retrieve {source_id}: {error}") from error
        if not content:
            raise RuleRetrievalError(f"Official source {source_id} returned no content")
        retrieved_at = datetime.now(UTC)
        self._cache[cache_key] = (final_url, content_type, content, retrieved_at)
        return RetrievedSource(
            source_id=source_id,
            title=title,
            publisher=publisher,
            url=final_url,
            content_type=content_type,
            content=content,
            retrieved_at=retrieved_at,
        )

    @staticmethod
    def _validate_https(url: str) -> None:
        if urlparse(url).scheme.lower() != "https":
            raise RuleRetrievalError("Public-rule sources must use HTTPS")
