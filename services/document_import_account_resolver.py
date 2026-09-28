"""Resolve the account identified by a supported import document."""

from __future__ import annotations

import sqlite3

from institution_support.registry import InstitutionRegistry
from repositories.account_repository import AccountRepository


class DocumentImportAccountResolver:
    """Find or create the account a document belongs to, using its importer's declaration."""

    def __init__(self, connection: sqlite3.Connection, registry: InstitutionRegistry) -> None:
        self._registry = registry
        self._accounts = AccountRepository(connection)

    def resolve(self, importer_name: str, content: bytes, filename: str) -> int:
        match = next(
            (
                (provider, importer)
                for provider, importer in self._registry.importers()
                if importer.importer_name == importer_name
            ),
            None,
        )
        if match is None:
            raise ValueError(f"Cannot auto-detect an account from {filename}")
        provider, importer = match
        read_account_number, account_type = importer.account_number, importer.account_type
        if read_account_number is None or account_type is None:
            raise ValueError(f"Cannot auto-detect an account from {filename}")
        institution = provider.display_name
        account_number = read_account_number(content, filename)
        existing = self._accounts.find_by_institution_number(institution, account_number)
        if existing:
            return existing.id
        return self._accounts.create(
            f"{institution} {account_number}",
            account_type,
            account_number=account_number,
            institution=institution,
        ).id
