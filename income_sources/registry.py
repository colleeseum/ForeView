# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from pathlib import Path

from domain.calver import is_calver
from domain.validation_error import ValidationError
from income_sources.income_source_provider import IncomeSourceProvider
from services.ufile_tax_return_parser import UFileTaxReturnParser

_UFIlE_HELP = (Path(__file__).with_name("ufile_help.md")).read_text(encoding="utf-8")


class IncomeSourceRegistry:
    """Resolve factual-income importers without coupling the UI to one format."""

    def __init__(self, providers: tuple[IncomeSourceProvider, ...]) -> None:
        for provider in providers:
            if not is_calver(provider.version):
                raise ValidationError(
                    "input_income_source_must_use_calver",
                    f"Income source '{provider.key}' must use CalVer",
                    detail0=provider.key,
                )
        self._providers = {provider.key: provider for provider in providers}

    @property
    def providers(self) -> tuple[IncomeSourceProvider, ...]:
        return tuple(self._providers.values())

    def get(self, key: str) -> IncomeSourceProvider:
        try:
            return self._providers[key]
        except KeyError as error:
            raise ValidationError(
                "input_unsupported_income_source", f"Unsupported income source: {key}", detail0=key
            ) from error

    def detect(self, content: bytes) -> IncomeSourceProvider:
        matches = tuple(
            provider
            for provider in self._providers.values()
            if provider.detects and provider.detects(content)
        )
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValidationError(
                "input_the_pdf_format_was_not_recognized_as_a_supported_t1_source",
                "The PDF format was not recognized as a supported T1 source",
            )
        raise ValidationError(
            "input_the_pdf_matches_more_than_one_income_source",
            "The PDF matches more than one income source",
        )


income_source_registry = IncomeSourceRegistry(
    (
        IncomeSourceProvider(
            key="ufile",
            display_name="UFile T1 PDF",
            translations={
                "fr-CA": {
                    "display_name": "PDF T1 UFile",
                    "help_text": (
                        "Comment télécharger le PDF UFile\n\n"
                        "1. Connectez-vous au compte UFile contenant la déclaration.\n"
                        "2. Ouvrez l’étape 4, Tax Return, puis la page Tax Return - view or download.\n"
                        "3. Dans Family members, sélectionnez la personne concernée.\n"
                        "4. Vérifiez son nom dans le titre et le texte de la déclaration.\n"
                        "5. Cliquez sur Taxpayer’s copy, save PDF dans Guidance and diagnostics.\n"
                        "6. Répétez la sélection et le téléchargement pour chaque personne.\n"
                        "7. Indiquez si possible le nom et l’année fiscale dans le nom du fichier.\n\n"
                        "Avant d’enregistrer les montants, vérifiez que la personne sélectionnée dans "
                        "ForeView correspond au PDF. Le document sert uniquement à la prévisualisation "
                        "et n’est pas conservé. Une différence de nom détectée bloque l’importation. "
                        "Si aucun nom n’est détecté, vérifiez vous-même le document.\n\n"
                        "Instructions vérifiées avec l’importateur : 2026-09-29."
                    ),
                }
            },
            parser=UFileTaxReturnParser().parse,
            source_label="UFile T1",
            help_text=_UFIlE_HELP,
            detects=UFileTaxReturnParser.detects,
            version="2026.09.29.1",
        ),
    )
)
