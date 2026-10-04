"""Generate invented bank documents for local parser integration tests."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SYNTHETIC_NOTICE = "SYNTHETIC TEST DOCUMENT - NO REAL FINANCIAL DATA"


def _write_pdf(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(path), pagesize=letter, pageCompression=0)
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


def create_synthetic_fixture_set(directory: Path) -> dict[str, Path]:
    """Create every supported synthetic PDF and CSV fixture."""
    directory.mkdir(parents=True, exist_ok=True)
    creators = {
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
