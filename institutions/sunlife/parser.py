"""Parsers for Sun Life Group Choices RRSP PDFs."""

import io
import re
from collections.abc import Iterable
from datetime import datetime

import pdfplumber


def _money(value: str) -> float:
    return float(value.replace(",", ""))


def parse_transaction_history(
    page_texts: Iterable[str], filename: str = "statement.pdf"
) -> dict[str, object]:
    text = "\n".join(page_texts).replace("\xa0", " ")
    if "View transaction history" not in text or "Group Choices Plan" not in text:
        raise ValueError(f"{filename} does not look like a Sun Life transaction history")
    account_match = re.search(r"Account\s*#:\s*(\d+)", text, re.IGNORECASE)
    if not account_match:
        raise ValueError(f"Could not read the Sun Life account number in {filename}")

    event_pattern = re.compile(
        r"^\s*(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})\s+(.+?)\s+\$([\d,]+\.\d{2})\s*$",
        re.MULTILINE,
    )
    matches = list(event_pattern.finditer(text))
    rows: list[dict[str, object]] = []
    for index, match in enumerate(matches):
        description = match.group(2).strip()
        if not description.upper().startswith("RRSP "):
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end]
        block = re.split(r"\n(?:Previous|Summary|Details|Funds with|https?://)", block, maxsplit=1)[
            0
        ]
        allocation_lines = [line.strip() for line in block.splitlines() if line.strip()]
        raw_description = " ".join([description, *allocation_lines])
        transaction_date = datetime.strptime(match.group(1), "%d %b %Y").date().isoformat()
        rows.append(
            {
                "date": transaction_date,
                "amount": _money(match.group(3)),
                "balance": None,
                "description": raw_description,
                "category": "Transfer",
                "transaction_type": "transfer",
            }
        )
    if not rows:
        raise ValueError(f"Could not read Sun Life transaction rows in {filename}")
    return {
        "account_number": account_match.group(1),
        "rows": rows,
    }


def is_transaction_history_pdf(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:2])
        return (
            "View transaction history" in text
            and "Group Choices Plan" in text
            and bool(re.search(r"Account\s*#:\s*\d+", text, re.IGNORECASE))
        )
    except Exception:
        return False


_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def _fund_code(name: str) -> str:
    code = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return code[:80] or "SUNLIFE_FUND"


def parse_rrsp_statement(
    page_texts: Iterable[str], filename: str = "statement.pdf"
) -> dict[str, object]:
    """Parse a cumulative Sun Life Group Choices RRSP statement.

    These statements provide a balance and holdings snapshot, but do not expose
    a transaction ledger. Transactions are therefore intentionally left empty.
    """
    text = "\n".join(page_texts).replace("\xa0", " ")
    if "Group Choices Plan" not in text or "Registered Retirement Savings Plan" not in text:
        raise ValueError(f"{filename} does not look like a Sun Life RRSP statement")
    account_match = re.search(r"Account\s*number:\s*(\d[\d\s]+)", text, re.IGNORECASE)
    period_match = re.search(
        rf"For the period\s+({_MONTHS})\s+(\d{{1,2}})\s+to\s+({_MONTHS})\s+(\d{{1,2}}),\s*(\d{{4}})",
        text,
        re.IGNORECASE,
    )
    if not account_match or not period_match:
        raise ValueError(f"Could not read the Sun Life RRSP identity or period in {filename}")
    year = int(period_match.group(5))
    start_date = (
        datetime.strptime(f"{period_match.group(1)} {period_match.group(2)} {year}", "%B %d %Y")
        .date()
        .isoformat()
    )
    end_date = (
        datetime.strptime(f"{period_match.group(3)} {period_match.group(4)} {year}", "%B %d %Y")
        .date()
        .isoformat()
    )

    opening_match = re.search(r"Value of my plan on\s+[^$]+\$([\d,]+\.\d{2})", text, re.IGNORECASE)
    closing_match = (
        re.search(
            r"Value of my plan on\s+[^$]+\$([\d,]+\.\d{2})",
            text[opening_match.end() :],
            re.IGNORECASE,
        )
        if opening_match
        else None
    )
    if not opening_match or not closing_match:
        raise ValueError(f"Could not read the Sun Life RRSP balances in {filename}")

    investments_match = re.search(
        r"My investments\s+(.*?)(?:Total investments\s+\$[\d,]+\.\d{2})", text, re.S | re.IGNORECASE
    )
    holdings: list[dict[str, object]] = []
    if investments_match:
        current_class = ""
        known_classes = {
            "Cash & equivalents",
            "Canadian equity",
            "International equity",
            "Balanced",
            "Fixed income",
            "U.S. equity",
            "Other",
        }
        for raw_line in investments_match.group(1).splitlines():
            line = " ".join(raw_line.split())
            if not line or line in {
                "PRICE ON VALUE ON",
                "INVESTMENT NAME NUMBER OF UNITS AUG 31, 2026 AUG 31, 2026",
            }:
                continue
            if line in known_classes:
                current_class = line
                continue
            cash_match = re.match(r"^Sun Life GDIA\s+-\s+-\s+\$([\d,]+\.\d{2})$", line)
            if cash_match:
                holdings.append(
                    {
                        "valuation_date": end_date,
                        "asset_class": "Cash & equivalents",
                        "fund_code": "CASH",
                        "fund_name": "Sun Life GDIA",
                        "units": 0.0,
                        "unit_price": 1.0,
                        "market_value": _money(cash_match.group(1)),
                        "allocation_pct": None,
                    }
                )
                continue
            holding_match = re.match(
                r"^(.*?)\s+([\d,]+\.\d{3,5})\s+\$([\d,]+\.\d{4})\s+\$([\d,]+\.\d{2})$", line
            )
            if holding_match and current_class:
                name = holding_match.group(1).strip()
                holdings.append(
                    {
                        "valuation_date": end_date,
                        "asset_class": current_class,
                        "fund_code": _fund_code(name),
                        "fund_name": name,
                        "units": _money(holding_match.group(2)),
                        "unit_price": _money(holding_match.group(3)),
                        "market_value": _money(holding_match.group(4)),
                        "allocation_pct": None,
                    }
                )
    return {
        "account_number": re.sub(r"\s+", "", account_match.group(1)),
        "statement_start": start_date,
        "statement_end": end_date,
        "opening_value": _money(opening_match.group(1)),
        "closing_value": _money(closing_match.group(1)),
        "rows": [],
        "holdings": holdings,
    }


def is_rrsp_statement_pdf(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:2])
        return (
            "Group Choices Plan" in text
            and "Registered Retirement Savings Plan" in text
            and "Value of my plan on" in text
            and bool(re.search(r"Account\s*number:\s*\d", text, re.IGNORECASE))
        )
    except Exception:
        return False
