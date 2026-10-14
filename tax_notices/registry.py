# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

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
            translations={
                "fr-CA": {
                    "display_name": "Avis de cotisation de l’ARC",
                    "help_text": "Téléchargez l’avis de cotisation individuel dans Mon dossier de l’ARC. "
                    "L’importateur lit les totaux fédéraux cotisés et, lorsqu’il est présent, le relevé "
                    "du maximum déductible au titre des REER. Le PDF, l’adresse, le numéro d’assurance "
                    "sociale et les identifiants du compte ARC ne sont pas conservés.",
                }
            },
            source_label="CRA NOA",
            parser=CraNoticeParser().parse,
            detects=CraNoticeParser.detects,
            help_text=(_ROOT / "cra_help.md").read_text(encoding="utf-8"),
        ),
        TaxNoticeProvider(
            key="revenu-quebec-noa",
            display_name="Revenu Québec notice of assessment",
            translations={
                "fr-CA": {
                    "display_name": "Avis de cotisation de Revenu Québec",
                    "help_text": "Téléchargez l’avis de cotisation individuel dans Mon dossier de Revenu "
                    "Québec. L’importateur lit les totaux québécois cotisés et conserve les cotisations "
                    "supplémentaires au RQAP séparément de l’impôt. Le PDF, l’adresse, le numéro "
                    "d’identification et le numéro de l’avis ne sont pas conservés.",
                }
            },
            source_label="Revenu Québec NOA",
            parser=RevenuQuebecNoticeParser().parse,
            detects=RevenuQuebecNoticeParser.detects,
            help_text=(_ROOT / "revenu_quebec_help.md").read_text(encoding="utf-8"),
        ),
    )
)
