from __future__ import annotations

from pathlib import Path

from domain.calver import is_calver
from income_sources.income_source_provider import IncomeSourceProvider
from services.ufile_tax_return_parser import UFileTaxReturnParser

_UFIlE_HELP = (Path(__file__).with_name("ufile_help.md")).read_text(encoding="utf-8")


class IncomeSourceRegistry:
    """Resolve factual-income importers without coupling the UI to one format."""

    def __init__(self, providers: tuple[IncomeSourceProvider, ...]) -> None:
        for provider in providers:
            if not is_calver(provider.version):
                raise ValueError(f"Income source '{provider.key}' must use CalVer")
        self._providers = {provider.key: provider for provider in providers}

    @property
    def providers(self) -> tuple[IncomeSourceProvider, ...]:
        return tuple(self._providers.values())

    def get(self, key: str) -> IncomeSourceProvider:
        try:
            return self._providers[key]
        except KeyError as error:
            raise ValueError(f"Unsupported income source: {key}") from error

    def detect(self, content: bytes) -> IncomeSourceProvider:
        matches = tuple(
            provider
            for provider in self._providers.values()
            if provider.detects and provider.detects(content)
        )
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError("The PDF format was not recognized as a supported T1 source")
        raise ValueError("The PDF matches more than one income source")


income_source_registry = IncomeSourceRegistry(
    (
        IncomeSourceProvider(
            key="ufile",
            display_name="UFile T1 PDF",
            parser=UFileTaxReturnParser().parse,
            source_label="UFile T1",
            help_text=_UFIlE_HELP,
            detects=UFileTaxReturnParser.detects,
            version="2026.09.29.1",
        ),
    )
)
