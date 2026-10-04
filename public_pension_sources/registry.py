from __future__ import annotations

from pathlib import Path

from domain.calver import is_calver
from public_pension_sources.public_pension_source_provider import PublicPensionSourceProvider
from services.retraite_quebec_statement_parser import RetraiteQuebecStatementParser

_HELP = (Path(__file__).parent / "retraite_quebec_help.md").read_text(encoding="utf-8")


class PublicPensionSourceRegistry:
    """Detect a supported CPP/QPP statement through registered providers."""

    def __init__(self, providers: tuple[PublicPensionSourceProvider, ...]) -> None:
        if any(not is_calver(provider.version) for provider in providers):
            raise ValueError("Public pension providers must use CalVer")
        self._providers = providers

    @property
    def providers(self) -> tuple[PublicPensionSourceProvider, ...]:
        return self._providers

    def detect(self, content: bytes) -> PublicPensionSourceProvider | None:
        matches = tuple(provider for provider in self._providers if provider.detects(content))
        if len(matches) > 1:
            raise ValueError("The PDF matches more than one public pension source")
        return matches[0] if matches else None


public_pension_source_registry = PublicPensionSourceRegistry(
    (
        PublicPensionSourceProvider(
            key="retraite-quebec-participation",
            display_name="Retraite Québec Statement of Participation",
            parser=RetraiteQuebecStatementParser().parse,
            detects=RetraiteQuebecStatementParser.detects,
            help_text=_HELP,
        ),
    )
)
