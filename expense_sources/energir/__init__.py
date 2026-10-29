# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Énergir natural-gas expense source."""

from pathlib import Path

from expense_sources.energir.parser import EnergirParser
from expense_sources.expense_source_provider import ExpenseSourceProvider


def provider() -> ExpenseSourceProvider:
    parser = EnergirParser()
    return ExpenseSourceProvider(
        key="energir",
        display_name="Énergir natural-gas bill",
        parser=parser.parse,
        detects=parser.detects,
        version=parser.VERSION,
        help_text=(Path(__file__).parent / "HELP.md").read_text(encoding="utf-8"),
        translations={
            "fr-CA": {
                "display_name": "Facture de gaz naturel d’Énergir",
                "help_text": "Téléchargez le PDF bilingue de deux pages dans votre espace client Énergir. Vérifiez le montant de gaz naturel, taxes incluses, et les dates avant de confirmer le nom, la catégorie et l’association. Le module n’utilise pas le solde, un paiement automatique ou le total à payer. Les trois mentions de période et le nombre de jours inclusifs doivent concorder. Les factures groupées, corrigées, avec location ou mode de paiements égaux ne sont pas prises en charge : saisissez-les manuellement. Les PDF numérisés ou les autres formats non vérifiés sont rejetés. Le PDF n’est pas conservé; seuls son nom, son empreinte, la version de l’analyseur et les dépenses confirmées sont retenus.",
            }
        },
    )


__all__ = ["EnergirParser", "provider"]
