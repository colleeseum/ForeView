# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Registry and discovery for household expense-statement sources."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable

from domain.calver import is_calver
from expense_sources.expense_source_provider import ExpenseSourceProvider


class ExpenseSourceRegistry:
    """Detect and parse supported household expense-statement PDFs."""

    def __init__(self, providers: Iterable[ExpenseSourceProvider]) -> None:
        registered: dict[str, ExpenseSourceProvider] = {}
        for provider in providers:
            if not provider.key.strip():
                raise ValueError("Expense source key is required")
            if not provider.display_name.strip():
                raise ValueError(f"Expense source '{provider.key}' requires a display name")
            if not is_calver(provider.version):
                raise ValueError(f"Expense source '{provider.key}' must use CalVer")
            if provider.key in registered:
                raise ValueError(f"Duplicate expense source key: {provider.key}")
            registered[provider.key] = provider
        self._providers = registered

    @property
    def providers(self) -> tuple[ExpenseSourceProvider, ...]:
        return tuple(self._providers.values())

    def get(self, key: str) -> ExpenseSourceProvider:
        try:
            return self._providers[key]
        except KeyError as error:
            raise ValueError(f"Unknown expense source: {key}") from error

    def detect(self, content: bytes) -> ExpenseSourceProvider:
        matches = tuple(
            provider for provider in self._providers.values() if provider.detects(content)
        )
        if len(matches) > 1:
            keys = ", ".join(provider.key for provider in matches)
            raise ValueError(f"The document matches multiple expense sources: {keys}")
        if not matches:
            raise ValueError("The uploaded PDF does not match any supported expense source")
        return matches[0]


def discover_expense_sources() -> ExpenseSourceRegistry:
    """Discover provider packages directly below :mod:`expense_sources`."""

    package = importlib.import_module("expense_sources")
    providers: list[ExpenseSourceProvider] = []
    ignored = {"expense_source_provider", "registry"}
    for module_info in pkgutil.iter_modules(package.__path__):
        if module_info.name in ignored:
            continue
        module = importlib.import_module(f"expense_sources.{module_info.name}")
        factory = getattr(module, "provider", None)
        if callable(factory):
            providers.append(factory())
    return ExpenseSourceRegistry(providers)


expense_source_registry = discover_expense_sources()
