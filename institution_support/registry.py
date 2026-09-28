"""Registry of institution providers and their optional capabilities."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Iterable

from institution_support.document_importer import DocumentImporter
from institution_support.institution_provider import InstitutionProvider

ProviderFactory = Callable[[], InstitutionProvider]


def _normalize(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


class InstitutionRegistry:
    """Validated lookup and document detection across institution providers."""

    def __init__(self, providers: Iterable[InstitutionProvider]) -> None:
        self._providers = tuple(providers)
        self._names: dict[str, InstitutionProvider] = {}
        importer_names: set[str] = set()
        for provider in self._providers:
            if not provider.key or not provider.display_name:
                raise ValueError("Institution providers require a key and display name")
            for name in provider.names():
                normalized = _normalize(name)
                existing = self._names.get(normalized)
                if existing and existing is not provider:
                    raise ValueError(f"Institution name '{name}' is already registered")
                self._names[normalized] = provider
            for importer in provider.importers:
                if importer.name in importer_names:
                    raise ValueError(f"Importer '{importer.name}' is already registered")
                importer_names.add(importer.name)

    @property
    def providers(self) -> tuple[InstitutionProvider, ...]:
        return self._providers

    def find(self, name: str) -> InstitutionProvider | None:
        return self._names.get(_normalize(name))

    def statement_sources(self) -> frozenset[str]:
        return frozenset(
            source for provider in self._providers for source in provider.statement_sources
        )

    def holds_securities(self, institution: str | None) -> bool:
        provider = self.find(institution) if institution else None
        return bool(provider and provider.holds_securities)

    def importers(
        self, institution: str | None = None
    ) -> tuple[tuple[InstitutionProvider, DocumentImporter], ...]:
        selected = self.find(institution) if institution else None
        providers = (selected,) if selected else (() if institution else self._providers)
        return tuple(
            (provider, importer)
            for provider in providers
            if provider is not None
            for importer in provider.importers
        )

    def import_help(self) -> str:
        descriptions = [
            topic.body
            for provider in self._providers
            for topic in provider.help_topics
            if topic.key == "imports"
        ]
        descriptions.append("Standard Date/Amount CSV files are also supported.")
        return "Supported formats include " + " ".join(descriptions)


def institution_registry(package: str = "institutions") -> InstitutionRegistry:
    """Build the registry from every institution module found in ``package``.

    Each module (a single file or a directory) must expose ``provider()`` returning
    its :class:`InstitutionProvider`, so adding an institution needs no edit here.
    Modules load in name order, which keeps document detection deterministic.
    Providers are rebuilt on each call so they pick up importer functions patched
    on their modules.
    """
    root = importlib.import_module(package)
    factories: list[ProviderFactory] = []
    for module_info in sorted(pkgutil.iter_modules(root.__path__), key=lambda info: info.name):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        factory = getattr(module, "provider", None)
        if not callable(factory):
            raise TypeError(f"Institution module '{module.__name__}' must define provider()")
        factories.append(factory)
    return InstitutionRegistry(factory() for factory in factories)
