# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Hydro-Québec factual-expense source provider."""

from pathlib import Path

from expense_sources.expense_source_provider import ExpenseSourceProvider
from expense_sources.hydro_qc.parser import HydroQuebecParser


def provider() -> ExpenseSourceProvider:
    parser = HydroQuebecParser()
    return ExpenseSourceProvider(
        key="hydro-quebec",
        display_name="Hydro-Québec electricity bill",
        translations={
            "fr-CA": {
                "display_name": "Facture d’électricité d’Hydro-Québec",
                "help_text": (
                    "Téléchargez le PDF de la facture depuis votre compte Hydro-Québec, puis "
                    "sélectionnez-le dans le dialogue d’importation. Vérifiez le montant, la période "
                    "de service, le nom, la catégorie et l’association avant d’enregistrer.\n\n"
                    "Les factures contenant plusieurs contrats ou périodes ne sont pas prises en "
                    "charge : saisissez chaque contrat manuellement.\n\n"
                    "Le module lit Montant de la présente facture ou Amount of this bill et la période "
                    "dans DÉTAIL DES COÛTS. Il n’utilise ni le solde antérieur, ni un paiement, ni le "
                    "montant total dû. Lorsque le nombre de jours imprimé l’exige, la période débute "
                    "le lendemain de la première date, qui correspond alors à une limite de relevé.\n\n"
                    "Les factures de révision annuelle du mode de versements égaux sont rejetées : "
                    "leur montant peut inclure un solde ou un ajustement d’une période antérieure.\n\n"
                    "Un format non pris en charge ou illisible est rejeté, sans valeurs devinées. "
                    "Le PDF n’est pas conservé. ForeView retient son nom de fichier, son empreinte, "
                    "la version de l’analyseur et les données de dépenses confirmées."
                ),
            }
        },
        parser=parser.parse,
        detects=parser.detects,
        help_text=(Path(__file__).parent / "HELP.md").read_text(encoding="utf-8"),
        version=parser.VERSION,
    )


__all__ = ["HydroQuebecParser", "provider"]
