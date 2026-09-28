"""One detectable document format supplied by an institution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Importer = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class DocumentImporter:
    """One detectable document format supplied by an institution."""

    name: str
    document_type: str
    detects: Callable[[bytes], bool]
    importer: Importer
    account_resolver: str
    help_text: str
    # Reads the account number from a document so an import can find or create
    # the account itself; None when the document does not identify an account.
    account_number: Callable[[bytes, str], str] | None = None
    # Account type for an account created from this document.
    account_type: str | None = None

    @property
    def importer_name(self) -> str:
        """Compatibility name used by the existing account resolver."""
        return self.account_resolver
