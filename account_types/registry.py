from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable

from .account_type_provider import AccountTypeProvider


class AccountTypeRegistry:
    """Validated lookup of account-type providers."""

    def __init__(self, providers: Iterable[AccountTypeProvider]) -> None:
        self._providers = tuple(providers)
        self._by_key: dict[str, AccountTypeProvider] = {}
        for provider in self._providers:
            if not provider.key or not provider.display_name:
                raise ValueError("Account types require a key and display name")
            if provider.key in self._by_key:
                raise ValueError(f"Account type '{provider.key}' is already registered")
            self._by_key[provider.key] = provider

    @property
    def providers(self) -> tuple[AccountTypeProvider, ...]:
        return self._providers

    def get(self, key: str) -> AccountTypeProvider:
        try:
            return self._by_key[key]
        except KeyError as error:
            raise ValueError(f"Unknown account type: {key}") from error

    def find(self, key: str | None) -> AccountTypeProvider | None:
        return self._by_key.get(key) if key is not None else None


def account_type_registry(package: str = "account_types") -> AccountTypeRegistry:
    root = importlib.import_module(package)
    providers: list[AccountTypeProvider] = []
    for module_info in sorted(pkgutil.iter_modules(root.__path__), key=lambda info: info.name):
        if module_info.name in {"account_type_provider", "registry"} or module_info.name.startswith(
            "_"
        ):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        factory = getattr(module, "provider", None)
        if not callable(factory):
            raise TypeError(f"Account-type module '{module.__name__}' must define provider()")
        providers.append(factory())
    return AccountTypeRegistry(providers)
