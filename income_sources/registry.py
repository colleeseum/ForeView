from __future__ import annotations

from income_sources.income_source_provider import IncomeSourceProvider
from services.ufile_tax_return_parser import UFileTaxReturnParser


class IncomeSourceRegistry:
    """Resolve factual-income importers without coupling the UI to one format."""

    def __init__(self, providers: tuple[IncomeSourceProvider, ...]) -> None:
        self._providers = {provider.key: provider for provider in providers}

    @property
    def providers(self) -> tuple[IncomeSourceProvider, ...]:
        return tuple(self._providers.values())

    def get(self, key: str) -> IncomeSourceProvider:
        try:
            return self._providers[key]
        except KeyError as error:
            raise ValueError(f"Unsupported income source: {key}") from error


income_source_registry = IncomeSourceRegistry(
    (
        IncomeSourceProvider(
            key="ufile",
            display_name="UFile T1 PDF",
            parser=UFileTaxReturnParser().parse,
            source_label="UFile T1",
        ),
    )
)
