# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Resolve the account identified by a supported import document."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from institution_support.registry import InstitutionRegistry
from repositories.account_repository import AccountRepository


@dataclass(frozen=True)
class AccountCreationRequired(ValueError):
    """Raised when an import identifies a new account that needs confirmation."""

    institution: str
    account_number: str
    account_type: str
    importer_name: str

    def __str__(self) -> str:
        return (
            f"The document identifies a new {self.account_type} account at "
            f"{self.institution} ({self.account_number})."
        )


class DocumentImportAccountResolver:
    """Find or create the account a document belongs to, using its importer's declaration."""

    def __init__(self, connection: sqlite3.Connection, registry: InstitutionRegistry) -> None:
        self._registry = registry
        self._accounts = AccountRepository(connection)

    def resolve(
        self,
        importer_name: str,
        content: bytes,
        filename: str,
        *,
        allow_create: bool = True,
    ) -> int:
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
        if not allow_create:
            raise AccountCreationRequired(
                institution, account_number, account_type, importer.importer_name
            )
        return self._accounts.create(
            f"{institution} {account_number}",
            account_type,
            account_number=account_number,
            institution=institution,
        ).id
