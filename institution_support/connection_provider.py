"""Runtime behaviour required from a connected institution adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class ConnectionProvider(Protocol):
    """Runtime behavior required from a connected institution adapter."""

    @property
    def institution_key(self) -> str: ...

    def configured_connections(self) -> tuple[str, ...]: ...

    def profile(self, connection_name: str) -> Mapping[str, str] | None: ...

    def status(self) -> dict[str, object]: ...

    def authorization_url(self, connection_name: str, state: str) -> str: ...

    def complete_authorization(self, connection_name: str, code: str) -> None: ...

    def refresh(self, connection_name: str) -> None: ...

    def synchronize(
        self, connection_name: str, *, fetch_from: str | None = None
    ) -> dict[str, object]:
        """Sync one connection; ``fetch_from`` (YYYY-MM-DD) re-fetches history from a date."""
        ...
