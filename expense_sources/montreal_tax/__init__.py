# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Montréal annual municipal-tax accounts."""

from pathlib import Path

from expense_sources.expense_source_provider import ExpenseSourceProvider
from expense_sources.montreal_tax.parser import MontrealTaxParser


def provider() -> ExpenseSourceProvider:
    parser = MontrealTaxParser()
    return ExpenseSourceProvider(
        key="montreal-tax",
        display_name="Montréal annual municipal-tax obligation",
        parser=parser.parse,
        detects=parser.detects,
        version=parser.VERSION,
        help_text=(Path(__file__).parent / "HELP.md").read_text(encoding="utf-8"),
        translations={
            "fr-CA": {
                "display_name": "Obligation annuelle de taxes municipales de Montréal",
                "help_text": "Téléchargez le compte annuel de taxes municipales de Montréal, puis ouvrez Dépenses > Charger un relevé de dépenses. Les formats vérifiés sont les PDF français et anglais de deux pages avec deux versements. La langue du document est indépendante de celle de l’interface; le nom proposé reste identique pour le même immeuble. Le total annuel est une obligation facturée, pas une preuve de paiement. Les lignes de taxes et les deux versements doivent concorder avec ce total. Le plan optionnel avec intérêts au verso et les coupons ne sont pas importés séparément. Vérifiez l’année, l’adresse et le numéro de compte dans le nom proposé, puis confirmez la catégorie et l’immeuble associé. Aucune association ni valeur immobilière n’est déduite automatiquement. Pour éviter un double compte, utilisez la même identité, catégorie et association pour les saisies manuelles et les versements de cette obligation; résolvez tout chevauchement. Le PDF n’est pas conservé. Les autres formats, comptes rectifiés, périodes partielles, relevés de solde, reçus, droits de mutation, taxes scolaires et PDF numérisés ne sont pas pris en charge.",
            }
        },
    )
