from __future__ import annotations

from pathlib import Path

from domain.calver import is_calver
from services.cra_notice_parser import CraNoticeParser
from services.revenu_quebec_notice_parser import RevenuQuebecNoticeParser
from tax_notices.tax_notice_provider import TaxNoticeProvider

_ROOT = Path(__file__).parent


class TaxNoticeRegistry:
    """Detect a supported assessment notice through registered providers."""

    def __init__(self, providers: tuple[TaxNoticeProvider, ...]) -> None:
        if any(not is_calver(provider.version) for provider in providers):
            raise ValueError("Tax notice providers must use CalVer")
        self._providers = providers

    @property
    def providers(self) -> tuple[TaxNoticeProvider, ...]:
        return self._providers

    def detect(self, content: bytes) -> TaxNoticeProvider | None:
        matches = tuple(provider for provider in self._providers if provider.detects(content))
        if len(matches) > 1:
            raise ValueError("The PDF matches more than one tax notice source")
        return matches[0] if matches else None


tax_notice_registry = TaxNoticeRegistry(
    (
        TaxNoticeProvider(
            key="cra-noa",
            display_name="CRA notice of assessment",
            source_label="CRA NOA",
            parser=CraNoticeParser().parse,
            detects=CraNoticeParser.detects,
            help_text=(_ROOT / "cra_help.md").read_text(encoding="utf-8"),
        ),
        TaxNoticeProvider(
            key="revenu-quebec-noa",
            display_name="Revenu Québec notice of assessment",
            source_label="Revenu Québec NOA",
            parser=RevenuQuebecNoticeParser().parse,
            detects=RevenuQuebecNoticeParser.detects,
            help_text=(_ROOT / "revenu_quebec_help.md").read_text(encoding="utf-8"),
        ),
    )
)
