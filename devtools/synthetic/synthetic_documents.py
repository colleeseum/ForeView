# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Generate invented bank documents for local parser integration tests."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SYNTHETIC_NOTICE = "SYNTHETIC TEST DOCUMENT - NO REAL FINANCIAL DATA"


def _write_pdf(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(path), pagesize=letter, pageCompression=1)
    document.setTitle(f"Synthetic fixture: {path.stem}")
    document.setAuthor("Retirement app synthetic fixture")
    document.setFont("Courier", 9)
    y = 756
    for line in [SYNTHETIC_NOTICE, "", *lines]:
        if y < 42:
            document.showPage()
            document.setFont("Courier", 9)
            y = 756
        document.drawString(36, y, line)
        y -= 15
    document.save()
    return path


def create_synthetic_eq_statement(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "January 2026 Statement",
            "Saving Account # 999-888-777 January 1, 2026 to January 31, 2026",
            "Activity details",
            "Date Description Withdrawals Deposits Balance",
            "Jan 12 Synthetic deposit $100.00 $1,100.00",
            "Jan 15 Synthetic withdrawal - $25.00 $1,075.00",
            "Jan 31 Interest received $2.50 $1,077.50",
        ],
    )


def create_synthetic_achieva_gic(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "Transactions",
            "24 Month TFSA GIC-SYN",
            "$10,450.00",
            "Wed, Aug 05, 2026",
            "System Generated Entry credit",
            "$450.00 $10,450.00",
            "interest 450.00",
            "Sat, Aug 05, 2023",
            "Tax Sheltered TFSA Transfer Credit",
            "$10,000.00 $10,000.00",
            "tfsa 0",
        ],
    )


def _create_synthetic_rbc_gic_history(path: Path, account_type: str) -> Path:
    return _write_pdf(
        path,
        [
            "Account Transaction History As of 24 Sep 2026",
            f"{account_type}.. 999888777",
            f"{account_type} Term Deposit #900000001",
            "Total",
            "Date Description Value",
            "Value",
            "24 Jul 2025 Opening Balance 9,800.00",
            "26 Sep 2025 GIC Interest Paid to Savings 400.00 10,200.00",
            "24 Sep 2026 Accrued Interest 250.00 10,450.00",
            "24 Sep 2026 Closing Balance 10,450.00",
            "RBC Savings Deposit",
            "Total",
            "Date Description Value",
            "Value",
            "24 Sep 2026 Interest 7.50 107.50",
            "24 Sep 2026 Closing Balance 107.50",
        ],
    )


def create_synthetic_rbc_gic_history(path: Path) -> Path:
    return _create_synthetic_rbc_gic_history(path, "TFSA")


def create_synthetic_rbc_resp_history(path: Path) -> Path:
    return _create_synthetic_rbc_gic_history(path, "RESP")


def create_synthetic_rbc_tfsa_statement(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "Votre relevé de placements",
            "1 janvier 2025 au 31 décembre 2025",
            "Votre n° de compte Votre succursale",
            "999888777 000RUEEXEMPLE",
            "Compte d'épargne libre d'impôt",
            "Total $10,000.00 $10,557.50 $557.50",
            "Activité de vos dépôts d'épargne",
            "30jun2025 Intérêtsréinvesti 2.50 105.00",
            "31déc2025 Intérêtsréinvesti 2.50 107.50",
            "31déc2025 Soldedeclôture 107.50",
            "Activité de vos CPG",
            "BanqueRoyaleCPG",
            "900000001 26sep2025 10,000.00 4.500 10,450.00 26sep2026 10,900.00",
        ],
    )


def create_synthetic_rbc_maturity_notice(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "Royal Bank of Canada",
            "GIC Maturity Notice",
            "Tax-Free Savings Account",
            "Account Number: 999888777",
            "Date: September 22, 2026",
            "TFSA Term Deposit",
            "Certificate #: 900000002 Issued by: Royal Bank of Canada Maturity Date: September 28, 2026",
            "Investment Date Amount Invested Interest Rate Maturity Value",
            "September 28, 2025 $5,000.00 4.000% $5,200.00",
            "Your maturity instruction",
        ],
    )


def create_synthetic_rbc_deposit_statement(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "Personal Deposit Account",
            "For August 15, 2026 - September 14, 2026",
            "Transit Number : 99999",
            "Account Number : 8888888",
            "Account Summary",
            "Opening Balance $1,000.00",
            "Total deposits Total withdrawals + $100.00 - $25.00",
            "Closing Balance $1,075.00",
        ],
    )


def create_synthetic_manulife_statement(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "Annual report:",
            "Manulife Financial Personal Plan",
            "Your customer number: 999000111",
            "January 1, 2025 to December 31, 2025",
            "Personal Registered Savings Plan (RRSP)",
            "What happened in your plan this period",
            "Opening value $50,000.00",
            "Plus money that went in $5,000.00",
            "Less money that came out $1,000.00",
            "Plus savings bonus $100.00",
            "Plus growth in value $5,900.00",
            "Value on December 31, 2025 $60,000.00",
            "Your plan assets are not locked in.",
            "Details of your investments",
            "Balanced",
            "1234 MLSynthetic Balanced Fund 600.00000 $100.0000 $60,000.00 100.00%",
            "Your current investment instructions",
        ],
    )


def create_synthetic_sunlife_statement(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "my statement",
            "Account number: 99900011122233",
            "Group Choices Plan",
            "EXAMPLE PERSON",
            "For the period January 1 to August 31, 2026",
            "Registered Retirement Savings Plan",
            "How my Registered Retirement Savings Plan's value changed this period",
            "Value of my plan on Jan 1, 2026 $80,000.00",
            "My investment gains and losses $10,000.00",
            "Value of my plan on Aug 31, 2026 $90,000.00",
            "My investments",
            "PRICE ON VALUE ON",
            "INVESTMENT NAME NUMBER OF UNITS AUG 31, 2026 AUG 31, 2026",
            "Cash & equivalents",
            "Sun Life GDIA - - $15,000.00",
            "Canadian equity",
            "Synthetic Canadian Equity 300.00000 $100.0000 $30,000.00",
            "Balanced",
            "Synthetic Balanced Fund 450.00000 $100.0000 $45,000.00",
            "Total investments $90,000.00",
            "About my plan",
        ],
    )


def create_synthetic_sunlife_history(path: Path) -> Path:
    return _write_pdf(
        path,
        [
            "View transaction history",
            "Group Choices Plan",
            "Account #: 99900011122233",
            "15 Aug 2026 RRSP Transfer in $2,500.00",
            "Synthetic Balanced Fund 100.00%",
            "Previous",
        ],
    )


def create_synthetic_hydro_qc_statement(path: Path) -> Path:
    """Create an invented statement shaped like a current Hydro-Québec bill."""

    return _write_pdf(
        path,
        [
            "Hydro-Québec",
            "Facture d'électricité du 2 février 2026",
            "Compte synthétique 999 888 777 000",
            "SOMMAIRE DE VOTRE FACTURE",
            "Coûts de l'électricité 26,96 $",
            "TPS 1,35 $",
            "TVQ 2,69 $",
            "Montant de la présente facture 31,00 $",
            "Amount of this bill",
            "Solde précédent 80,00 $",
            "Montant total à payer 111,00 $",
            "DÉTAIL DES COÛTS - TARIF DOMESTIQUE D",
            "Du 31 décembre 2025 au 31 janvier 2026 (31 jours)",
            "DETAILS OF COSTS - DOMESTIC RATE D",
        ],
    )


def create_synthetic_energir_statement(path: Path, *, front_note: str = "") -> Path:
    """Invent a bilingual two-page gas bill, including an automatic payment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(path), pagesize=letter, pageCompression=1)
    document.setTitle("Synthetic Énergir fixture")
    for lines in (
        [
            SYNTHETIC_NOTICE,
            "Énergir, s.e.c. / Énergir, L.P.",
            "Facture émise le 2026 JA 16",
            "Pour la période du 2025 DE 15 au / to 2026 JA 14",
            "For the period of",
            "Facture no / Bill # 000000000001",
            "Alex Example - Synthetic address",
            front_note,
            "Historique de consommation / Consumption History",
            "2025 NO 15 2025 DE 14 30 80R 90,00",
            "Détails du solde précédent / Previous balance details",
            "Solde précédent 90,00 $",
            "Paiement reçu / Payment received 90,00 $CR",
            "Détails du montant courant",
            "2025 OC 15 2025 NO 14 31 90R 85,00 Current amount details",
            "Montant facturé pour la période du /",
            "Amount Billed for the Period from",
            "2025 DE 15 au / to 2026 JA 14",
            "Volume facturé / Volume billed: 100 m3 (voir verso / see reverse) 100,00 $",
            "TPS / GST (no / # 000000001) 5,00 $",
            "Total de l'année courante / Total of Current Year TVQ / PST (no / # 000000002) 9,98 $",
            "2024 DE 15 2025 DE 14 365 1500 1 999,99 Total 114,98 $ 114,98 $",
            "Montant courant / Current amount 114,98 $",
            "Prélèvement automatique / Automatic payment 114,98 $CR",
            "Montant total à payer / Total Amount to Pay 0,00 $",
        ],
        [
            SYNTHETIC_NOTICE,
            "Énergir - Numéro de compte / Account number : 0000 0000 001",
            "Période / Period : 2025 DE 15 au / to 2026 JA 14 31 jours / days",
            "Calcul du volume facturé / Calculation of the Billed Volume",
            "Détail du calcul du montant facturé / Calculation of the Amount Billed",
            "Gaz naturel fourni / Natural Gas Supplied",
            "Distribution total 60,00 $",
            "Total avant taxes / Total before taxes 100,00 $",
        ],
    ):
        document.setFont("Helvetica", 10)
        for index, line in enumerate(lines):
            document.drawString(30, 760 - index * 22, line)
        document.showPage()
    document.save()
    return path


def create_synthetic_montreal_tax_statement(
    path: Path, *, total: str = "4 000,03", language: str = "en"
) -> Path:
    """Invent an annual obligation with unequal installments and separate coupons."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(path), pagesize=(612, 1008), pageCompression=1)
    document.setTitle("Synthetic Montréal annual municipal-tax account")
    translations = {
        "Municipal Tax Account 2026": "Compte de taxes municipales 2026",
        "Account number Reference number Access code Taxation period Billing date": "Numéro de compte Numéro de référence Code d'accès Période d'imposition Date de facturation",
        "000001-00 00000001-26-01-00 Day Month Year Day Month Year Day Month Year": "000001-00 00000001-26-01-00 Jour Mois Année Jour Mois Année Jour Mois Année",
        "01 01 2026 to 31 12 2026 28 01 2026": "01 01 2026 au 31 12 2026 28 01 2026",
        "Debtor(s) of the account": "Débiteur(s) du compte",
        "Property location": "Emplacement de la propriété",
        "Borough: Synthetic Borough": "Arrondissement : Quartier fictif",
        "Taxable value(s) on December 31, 2025: 600 000": "Valeur(s) imposable(s) au 31 décembre 2025 : 600 000",
        "Breakdown of account (See the appendix) Tax base Rate Amount": "Détail du compte (Consulter l'annexe jointe au compte) Base d'imposition Taux Montant",
        "GENERAL TAX 600 000 0,5000 /$100 3 000,01": "TAXE GÉNÉRALE 600 000 0,5000 /100$ 3 000,01",
        "TAX CONTRIBUTION 600 000 0,0167 /$100 100,01": "TAXE CONTRIBUTION 600 000 0,0167 /100$ 100,01",
        "BOROUGH": "ARRONDISSEMENT",
        "TAX CONCERNING SERVICES 600 000 0,1500 /$100 900,01": "TAXE RELATIVE AUX SERVICES 600 000 0,1500 /100$ 900,01",
        "Due date(s) Day Month Year Amount Day Month Year Amount Account total": "Total du compte\nDate(s) limite(s) Jour Mois Année Montant Jour Mois Année Montant",
        f"1st: 02 03 2026 2 000,01 2nd: 01 06 2026 2 000,02 {total}": f"versement(s) 1er : 02 03 2026 2 000,01 2e : 01 06 2026 2 000,02 {total}",
        "Interest and penalty may apply to overdue payments.": "Tout versement tardif entraîne des intérêts et pénalités.",
        "This account must be paid in full.": "Ce compte doit être payé en totalité.",
        "2nd Instalment - Please attach to your 2nd payment": "Versement 2 - À joindre à votre 2e paiement",
        "1st Instalment - Please attach to your 1st payment": "Versement 1 - À joindre à votre 1er paiement",
        "Reference number - Online payment 00000001-26-01-00": "Numéro de référence - Paiement Internet 00000001-26-01-00",
        "Instalment payable Amount paid": "Montant à payer Montant versé",
        "Terms of payment": "Modalités de paiement",
        "Option - 6 instalments with interests and penalty": "Option - 6 versements avec intérêts et pénalité",
        "Optional monthly payment $700,00 including interest and fees.": "Paiement mensuel optionnel de 700,00 $ avec intérêts et frais.",
        "The downloadable account does not include payments or later changes.": "La copie téléchargée ne comprend ni paiements ni modifications ultérieures.",
    }

    def draw(x: float, y: float, value: str) -> None:
        translated = translations.get(value, value) if language == "fr" else value
        for offset, line in enumerate(translated.splitlines()):
            document.drawString(x, y - offset * 11, line)

    document.setFont("Helvetica", 9)
    for index, line in enumerate(
        [
            SYNTHETIC_NOTICE,
            "Municipal Tax Account 2026",
            "Account number Reference number Access code Taxation period Billing date",
            "000001-00 00000001-26-01-00 Day Month Year Day Month Year Day Month Year",
            "01 01 2026 to 31 12 2026 28 01 2026",
        ]
    ):
        draw(30, 980 - index * 20, line)
    draw(30, 870, "Debtor(s) of the account")
    # The real source has a sub-point offset between header and value columns.
    draw(310.01, 870, "Property location")
    # Both columns share a text line. The importer must not absorb the debtor's name.
    draw(30, 850, "Alex Example")
    draw(310, 850, "123 Example Street")
    draw(310, 830, "Borough: Synthetic Borough")
    for index, line in enumerate(
        [
            "Taxable value(s) on December 31, 2025: 600 000",
            "Breakdown of account (See the appendix) Tax base Rate Amount",
            "VILLE DE MONTRÉAL",
            "GENERAL TAX 600 000 0,5000 /$100 3 000,01",
            "TAX CONTRIBUTION 600 000 0,0167 /$100 100,01",
            "BOROUGH",
            "TAX CONCERNING SERVICES 600 000 0,1500 /$100 900,01",
            "Due date(s) Day Month Year Amount Day Month Year Amount Account total",
            f"1st: 02 03 2026 2 000,01 2nd: 01 06 2026 2 000,02 {total}",
            "Interest and penalty may apply to overdue payments.",
            "This account must be paid in full.",
            "2nd Instalment - Please attach to your 2nd payment",
            "Reference number - Online payment 00000001-26-01-00",
            "Instalment payable Amount paid",
            "2 000,02",
            "1st Instalment - Please attach to your 1st payment",
            "Instalment payable Amount paid",
            "2 000,01",
        ]
    ):
        draw(30, 790 - index * 28, line)
    document.showPage()
    document.setFont("Helvetica", 10)
    for index, line in enumerate(
        [
            SYNTHETIC_NOTICE,
            "Terms of payment",
            "Option - 6 instalments with interests and penalty",
            "Optional monthly payment $700,00 including interest and fees.",
            "The downloadable account does not include payments or later changes.",
        ]
    ):
        draw(30, 960 - index * 25, line)
    document.save()
    return path


def create_synthetic_montreal_tax_statement_fr(path: Path) -> Path:
    """Create the French form of the invented annual obligation."""
    return create_synthetic_montreal_tax_statement(path, language="fr")


def create_synthetic_fixture_set(directory: Path) -> dict[str, Path]:
    """Create every supported synthetic PDF and CSV fixture."""
    directory.mkdir(parents=True, exist_ok=True)
    creators = {
        "montreal_tax_fr_pdf": (
            "montreal-municipal-tax-fr.pdf",
            create_synthetic_montreal_tax_statement_fr,
        ),
        "montreal_tax_pdf": ("montreal-municipal-tax.pdf", create_synthetic_montreal_tax_statement),
        "energir_pdf": ("energir-gas-bill.pdf", create_synthetic_energir_statement),
        "eq_pdf": ("eq-monthly-statement.pdf", create_synthetic_eq_statement),
        "achieva_gic_pdf": ("achieva-gic-history.pdf", create_synthetic_achieva_gic),
        "rbc_gic_pdf": ("rbc-gic-history.pdf", create_synthetic_rbc_gic_history),
        "rbc_resp_pdf": ("rbc-resp-history.pdf", create_synthetic_rbc_resp_history),
        "rbc_tfsa_pdf": ("rbc-tfsa-statement.pdf", create_synthetic_rbc_tfsa_statement),
        "rbc_maturity_pdf": ("rbc-gic-maturity-notice.pdf", create_synthetic_rbc_maturity_notice),
        "rbc_deposit_pdf": ("rbc-deposit-statement.pdf", create_synthetic_rbc_deposit_statement),
        "manulife_pdf": ("manulife-rrsp-statement.pdf", create_synthetic_manulife_statement),
        "sunlife_pdf": ("sunlife-rrsp-statement.pdf", create_synthetic_sunlife_statement),
        "sunlife_history_pdf": (
            "sunlife-transaction-history.pdf",
            create_synthetic_sunlife_history,
        ),
        "hydro_qc_pdf": (
            "hydro-quebec-electricity-bill.pdf",
            create_synthetic_hydro_qc_statement,
        ),
    }
    fixtures = {key: creator(directory / filename) for key, (filename, creator) in creators.items()}
    csv_content = {
        "generic_balanced_csv": (
            "generic-with-balances.csv",
            b"Date,Amount,Description,Balance\n2026-01-01,100.00,Deposit,1100.00\n2026-01-02,-25.00,Purchase,1075.00\n",
        ),
        "generic_calculated_csv": (
            "generic-without-balances.csv",
            b"Date,Amount,Description\n2026-01-01,100.00,Deposit\n2026-01-02,-25.00,Purchase\n",
        ),
        "rbc_csv": (
            "rbc-canada.csv",
            "Date de l'opération,Numéro du compte,CAD$,Description 1,Description 2\n08/20/2026,999998888888,100.00,Synthetic,deposit\n08/25/2026,999998888888,-25.00,Synthetic,purchase\n".encode(),
        ),
    }
    for key, (filename, content) in csv_content.items():
        fixtures[key] = directory / filename
        fixtures[key].write_bytes(content)
    return fixtures
