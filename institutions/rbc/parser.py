# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Parsers for RBC transaction and investment documents."""

import io
import re
from collections.abc import Iterable
from datetime import date, datetime

import pdfplumber


def _money(value: object) -> float:
    return float(str(value).replace(",", ""))


def parse_gic_transaction_history(
    page_texts: Iterable[str], filename: str = "statement.pdf"
) -> dict[str, object]:
    """Parse RBC Online Banking transaction history for one GIC."""
    text = "\n".join(page_texts).replace("\xa0", " ")
    account_match = re.search(r"Account Transaction History.*?(TFSA|RESP)\.\.\s*(\d+)", text, re.S)
    if not account_match or "RBC Savings Deposit" not in text:
        raise ValueError(f"{filename} does not look like an RBC GIC transaction history")
    gic_section = text.split("RBC Savings Deposit", 1)[0]
    savings_section = text.split("RBC Savings Deposit", 1)[1]
    title_match = re.search(r"\n([^\n]+#\d+)\s*\nTotal\s*\nDate Description Value", gic_section)
    if not title_match:
        raise ValueError(f"Could not read the RBC GIC section in {filename}")
    date_pattern = re.compile(
        r"^(\d{1,2} [A-Z][a-z]{2} \d{4})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?$"
    )
    rows: list[dict[str, object]] = []
    savings_rows: list[dict[str, object]] = []
    closing_value = None
    closing_date = None
    for line in gic_section.splitlines():
        match = date_pattern.match(line.strip())
        if not match:
            continue
        transaction_date = datetime.strptime(match.group(1), "%d %b %Y").date().isoformat()
        description = match.group(2).strip()
        amount = _money(match.group(3))
        balance = _money(match.group(4)) if match.group(4) else None
        if description == "Closing Balance":
            closing_value, closing_date = balance or amount, transaction_date
            continue
        if description == "Opening Balance":
            continue
        transaction_type = "transfer" if "Maturity Value Reinvested" in description else "interest"
        rows.append(
            {
                "date": transaction_date,
                "amount": amount,
                "balance": balance,
                "description": description,
                "category": "Transfer" if transaction_type == "transfer" else "Interest",
                "transaction_type": transaction_type,
            }
        )
    if closing_value is None or not rows:
        raise ValueError(f"Could not read RBC GIC transactions in {filename}")
    savings_match = re.search(r"Closing Balance\s+([\d,]+\.\d{2})", savings_section)
    for line in savings_section.splitlines():
        match = date_pattern.match(line.strip())
        if not match or match.group(2) in {"Opening Balance", "Closing Balance"}:
            continue
        transaction_date = datetime.strptime(match.group(1), "%d %b %Y").date().isoformat()
        description = match.group(2).strip()
        amount = _money(match.group(3))
        balance = _money(match.group(4)) if match.group(4) else None
        savings_rows.append(
            {
                "date": transaction_date,
                "amount": amount,
                "balance": balance,
                "description": description,
                "category": "Interest",
                "transaction_type": "interest",
            }
        )
    certificate_match = re.search(r"#(\d+)", title_match.group(1))
    return {
        "account_type": account_match.group(1).lower(),
        "account_number": account_match.group(2),
        "certificate": certificate_match.group(1) if certificate_match else None,
        "gic_name": title_match.group(1).strip(),
        "redeemable": "redeemable" in title_match.group(1).lower(),
        "closing_value": closing_value,
        "statement_date": closing_date,
        "savings_closing": _money(savings_match.group(1)) if savings_match else None,
        "savings_rows": savings_rows,
        "rows": rows,
    }


def parse_deposit_statement_text(text: str, filename: str = "statement.pdf") -> dict[str, object]:
    """Extract stable summary fields from an RBC monthly deposit statement."""
    text = text.replace("\xa0", " ")
    english = "Personal Deposit Account" in text and "Account Summary" in text
    french = "Compte de dépôt de particulier" in text and "Sommaire du compte" in text
    if not english and not french:
        raise ValueError(f"{filename} does not look like an RBC deposit statement")
    if english:
        period = re.search(
            r"For\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*-\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            text,
        )
        account_match = re.search(
            r"Transit Number\s*:\s*(\d+).*?Account Number\s*:\s*(\d+)", text, re.S
        )
        opening = re.search(r"Opening Balance.*?\$([\d,]+\.\d{2})", text, re.S)
        closing = re.search(r"Closing Balance.*?\$([\d,]+\.\d{2})", text, re.S)
        totals = re.search(
            r"Total deposits.*?Total withdrawals.*?\+\s*\$([\d,]+\.\d{2}).*?-\s*\$([\d,]+\.\d{2})",
            text,
            re.S,
        )

        def parse_date(value: str) -> str:
            for date_format in ("%B %d, %Y", "%b %d, %Y"):
                try:
                    return datetime.strptime(value, date_format).date().isoformat()
                except ValueError:
                    continue
            raise ValueError(f"Unsupported RBC statement date: {value}")

        def amount(match: re.Match[str], group: int = 1) -> float:
            return _money(match.group(group))

    else:
        period = re.search(
            r"Compte de dépôt de particulier\s*\|\s*(\d{1,2}\s+[^\s]+\s+\d{4})\s*-\s*(\d{1,2}\s+[^\s]+\s+\d{4})",
            text,
        )
        account_match = re.search(
            r"Numéro de transit\s*:\s*(\d+).*?Numéro de compte\s*:\s*(\d+)", text, re.S
        )
        french_money = r"([\d ]+,\d{2})\s*\$"
        opening = re.search(r"Solde d’ouverture.*?" + french_money, text, re.S)
        closing = re.search(r"Solde de clôture.*?" + french_money, text, re.S)
        totals = None
        french_months = {
            "janvier": "January",
            "février": "February",
            "mars": "March",
            "avril": "April",
            "mai": "May",
            "juin": "June",
            "juillet": "July",
            "août": "August",
            "sept.": "September",
            "septembre": "September",
            "octobre": "October",
            "novembre": "November",
            "décembre": "December",
        }

        def parse_date(value: str) -> str:
            day, month, year = value.split()
            return (
                datetime.strptime(f"{day} {french_months[month.lower()]} {year}", "%d %B %Y")
                .date()
                .isoformat()
            )

        def amount(match: re.Match[str], group: int = 1) -> float:
            return float(match.group(group).replace(" ", "").replace(",", "."))

    if not period or not account_match or not opening or not closing:
        raise ValueError(f"Could not read the RBC statement summary in {filename}")
    return {
        "account_number": f"{account_match.group(1)}-{account_match.group(2)}",
        "statement_start": parse_date(period.group(1)),
        "statement_end": parse_date(period.group(2)),
        "opening_balance": amount(opening),
        "closing_balance": amount(closing),
        "statement_deposits": amount(totals) if totals else None,
        "statement_withdrawals": amount(totals, 2) if totals else None,
    }


_FRENCH_MONTHS = {
    "jan": 1,
    "janvier": 1,
    "fév": 2,
    "févr": 2,
    "février": 2,
    "mar": 3,
    "mars": 3,
    "avr": 4,
    "avril": 4,
    "mai": 5,
    "jun": 6,
    "juin": 6,
    "jui": 7,
    "juil": 7,
    "juillet": 7,
    "aoû": 8,
    "août": 8,
    "sep": 9,
    "sept": 9,
    "septembre": 9,
    "oct": 10,
    "octobre": 10,
    "nov": 11,
    "novembre": 11,
    "déc": 12,
    "dec": 12,
    "décembre": 12,
}


def _parse_french_compact_date(value: str, default_year: int | None = None) -> str:
    compact = re.sub(r"\s+", "", value.strip().lower().replace(".", ""))
    match = re.fullmatch(r"(\d{1,2})([a-zéû]+)(\d{4})?", compact)
    if not match or match.group(2) not in _FRENCH_MONTHS:
        raise ValueError(f"Unsupported French date: {value}")
    year = int(match.group(3) or default_year or 0)
    if not year:
        raise ValueError(f"Year is missing from date: {value}")
    return date(year, _FRENCH_MONTHS[match.group(2)], int(match.group(1))).isoformat()


def _french_statement_money(value: str) -> float:
    return float(value.replace(" ", "").replace(",", "."))


def parse_tfsa_statement(
    page_texts: Iterable[str], filename: str = "statement.pdf"
) -> dict[str, object]:
    """Parse RBC French TFSA investment statements and CPG maturity notices."""
    pages = list(page_texts)
    text = "\n".join(pages).replace("\xa0", " ")
    is_french_tfsa = "Compte d'épargne libre d'impôt" in text
    is_english_maturity_notice = (
        "GIC Maturity Notice" in text and "Tax-Free Savings Account" in text
    )
    if not is_french_tfsa and not is_english_maturity_notice:
        raise ValueError(f"{filename} does not look like an RBC TFSA investment document")
    account_match = re.search(r"Numéro de compte\s*:\s*(\d+)", text)
    if not account_match:
        account_match = re.search(r"Account Number:\s*(\d+)", text)
    if not account_match:
        account_match = re.search(r"Votre n° de compte\s+Votre succursale\s*\n(\d+)", text)
    if not account_match:
        raise ValueError(f"Could not read the RBC TFSA account number in {filename}")
    notice_match = re.search(r"Date de l’avis\s*:\s*(\d{1,2})\s+([^,]+),\s*(\d{4})", text)
    if not notice_match:
        notice_match = re.search(r"Date:\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})", text)
    statement_match = re.search(
        r"(\d{1,2})\s+janvier\s+(\d{4})\s+au\s+(\d{1,2})\s+décembre\s+(\d{4})", text
    )
    result: dict[str, object] = {
        "account_number": account_match.group(1),
        "statement_start": None,
        "statement_end": None,
        "opening_value": None,
        "closing_value": None,
        "savings_closing": None,
        "savings_events": [],
        "gics": [],
        "document_type": "statement" if statement_match else "maturity_notice",
    }
    savings_events = result["savings_events"]
    gics = result["gics"]
    assert isinstance(savings_events, list)
    assert isinstance(gics, list)
    if statement_match:
        result["statement_start"] = date(
            int(statement_match.group(2)), 1, int(statement_match.group(1))
        ).isoformat()
        result["statement_end"] = date(
            int(statement_match.group(4)), 12, int(statement_match.group(3))
        ).isoformat()
        total_match = re.search(
            r"Total\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})", text
        )
        if total_match:
            result["opening_value"] = _money(total_match.group(1))
            result["closing_value"] = _money(total_match.group(2))
        savings_match = re.search(
            r"Activité de vos dépôts d'épargne(.*?)(?:Activité de vos CPG|Page\s+\d+\s+de\s+\d+)",
            text,
            re.S,
        )
        if savings_match:
            event_pattern = re.compile(
                r"^(\d{1,2}[a-zéû]+\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
            )
            for line in savings_match.group(1).splitlines():
                match = event_pattern.match(line.strip())
                if match:
                    savings_events.append(
                        {
                            "date": _parse_french_compact_date(match.group(1)),
                            "description": {
                                "Intérêtsréinvesti": "Interest reinvested",
                                "IntérêtsCPGversésàl'épargne": "GIC interest paid to savings",
                            }.get(match.group(2).strip(), match.group(2).strip()),
                            "amount": _money(match.group(3)),
                            "balance": _money(match.group(4)),
                        }
                    )
            closing_match = re.search(r"Soldedeclôture\s+([\d,]+\.\d{2})", savings_match.group(1))
            if closing_match:
                result["savings_closing"] = _money(closing_match.group(1))
    notice_year = int(notice_match.group(3)) if notice_match else None
    statement_gic_pattern = re.compile(
        r"BanqueRoyaleCPG\s+(\d{9})\s+(\d{1,2}[a-zéû]+\d{4})\s+"
        r"([\d,]+\.\d{2})\s+([\d.]+)\s+([\d,]+\.\d{2})\s+"
        r"(\d{1,2}[a-zéû]+\d{4})\s+([\d,]+\.\d{2})"
    )
    gic_match = statement_gic_pattern.search(text)
    if gic_match:
        gics.append(
            {
                "certificate": gic_match.group(1),
                "start_date": _parse_french_compact_date(gic_match.group(2)),
                "principal": _money(gic_match.group(3)),
                "interest_rate": float(gic_match.group(4)) / 100,
                "value_at_statement": _money(gic_match.group(5)),
                "maturity_date": _parse_french_compact_date(gic_match.group(6)),
                "maturity_value": _money(gic_match.group(7)),
                "redeemable": bool(re.search(r"Remboursable", text, re.IGNORECASE)),
            }
        )
    elif notice_match:
        certificate_match = re.search(r"Numéro de certificate\s*:\s*(\d+)", text)
        maturity_match = re.search(r"Date d’échéance\s*:\s*(\d{1,2})\s+([^,]+),", text)
        investment_match = re.search(
            r"(\d{1,2})\s+([^,]+),\s*(\d{4})\s+([\d ]+,\d{2})\s*\$\s*"
            r"([\d.,]+)\s*%\s*([\d ]+,\d{2})\s*\$",
            text,
        )
        if is_english_maturity_notice:
            certificate_match = re.search(r"Certificate\s*#:\s*(\d+)", text)
            maturity_match = re.search(
                r"Maturity Date:\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})", text
            )
            investment_match = re.search(
                r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+\$([\d,]+\.\d{2})\s+"
                r"([\d.]+)%\s+\$([\d,]+\.\d{2})",
                text,
            )
        if certificate_match and maturity_match and investment_match:
            if is_english_maturity_notice:
                maturity_date = date(
                    int(maturity_match.group(3)),
                    datetime.strptime(maturity_match.group(1), "%B").month,
                    int(maturity_match.group(2)),
                ).isoformat()
                start_date = date(
                    int(investment_match.group(3)),
                    datetime.strptime(investment_match.group(1), "%B").month,
                    int(investment_match.group(2)),
                ).isoformat()
                principal = _money(investment_match.group(4))
                interest_rate = float(investment_match.group(5)) / 100
                maturity_value = _money(investment_match.group(6))
            else:
                assert notice_year is not None
                maturity_date = date(
                    notice_year,
                    _FRENCH_MONTHS[maturity_match.group(2).lower()],
                    int(maturity_match.group(1)),
                ).isoformat()
                start_date = date(
                    int(investment_match.group(3)),
                    _FRENCH_MONTHS[investment_match.group(2).lower()],
                    int(investment_match.group(1)),
                ).isoformat()
                principal = _french_statement_money(investment_match.group(4))
                interest_rate = float(investment_match.group(5).replace(",", ".")) / 100
                maturity_value = _french_statement_money(investment_match.group(6))
            gics.append(
                {
                    "certificate": certificate_match.group(1),
                    "start_date": start_date,
                    "principal": principal,
                    "interest_rate": interest_rate,
                    "value_at_statement": None,
                    "maturity_date": maturity_date,
                    "maturity_value": maturity_value,
                    "redeemable": bool(re.search(r"Remboursable", text, re.IGNORECASE)),
                }
            )
    if not gics and result["document_type"] == "maturity_notice":
        raise ValueError(f"Could not read the RBC TFSA CPG details in {filename}")
    if result["document_type"] == "statement" and result["closing_value"] is None:
        raise ValueError(f"Could not read the RBC TFSA statement totals in {filename}")
    return result


def is_gic_transaction_history_pdf(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:1])
        return (
            "Account Transaction History" in text
            and "RBC Savings Deposit" in text
            and "Closing Balance" in text
        )
    except Exception:
        return False


def is_resp_gic_transaction_history_pdf(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:1])
        return (
            "Account Transaction History" in text
            and "RESP.." in text
            and "RBC Savings Deposit" in text
            and "Closing Balance" in text
        )
    except Exception:
        return False


def is_tfsa_gic_transaction_history_pdf(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:1])
        return (
            "Account Transaction History" in text
            and "TFSA.." in text
            and "RBC Savings Deposit" in text
            and "Closing Balance" in text
        )
    except Exception:
        return False
