"""Parser for Manulife Personal Plan RRSP progress and annual statements."""

import io
import re
from collections.abc import Iterable
from datetime import date, datetime

import pdfplumber


def _money(value: str) -> float:
    return float(value.replace(",", ""))


def _parse_holdings(text: str, statement_end: str) -> list[dict[str, object]]:
    """Read the holdings table from Manulife annual and semiannual statements."""
    match = re.search(
        r"(?:Details\s*(?:of\s*)?(?:your\s*)?investments)(.*?)(?:Your\s*current\s*investment\s*instructions|Your\s*current\s*investment)",
        text,
        re.S | re.I,
    )
    if not match:
        return []
    body = match.group(1)
    holdings: list[dict[str, object]] = []
    row_pattern = re.compile(
        r"(\d{4})\s*(?=ML)(.*?)\s+([\d,]+\.\d{3,5})\s+\$?([\d,]+\.\d{4})\s+\$([\d,]+\.\d{2})\s+(\d+\.\d+)%",
        re.S,
    )
    asset_class = ""
    known_classes = (
        "Target Date Funds",
        "Balanced",
        "Cdn Lrg Cap Eqty",
        "US Large Cap Eqty",
        "Global Equity",
    )
    for row in row_pattern.finditer(body):
        name = " ".join(row.group(2).split())
        if not name or name.startswith("Total"):
            continue
        prefix = body[max(0, row.start() - 100) : row.start()]
        suffix_class = next(
            (candidate for candidate in known_classes if name.endswith(candidate)), None
        )
        if suffix_class:
            asset_class = suffix_class
            name = name[: -len(suffix_class)].strip()
        else:
            for candidate in known_classes:
                if candidate in prefix:
                    asset_class = candidate
                    break
        holdings.append(
            {
                "valuation_date": statement_end,
                "asset_class": asset_class,
                "fund_code": row.group(1),
                "fund_name": name,
                "units": float(row.group(3).replace(",", "")),
                "unit_price": _money(row.group(4)),
                "market_value": _money(row.group(5)),
                "allocation_pct": float(row.group(6)),
            }
        )
    return holdings


def parse_rrsp_statement(
    page_texts: Iterable[str], filename: str = "statement.pdf"
) -> dict[str, object]:
    text = "\n".join(page_texts).replace("\xa0", " ")
    if "Manulife Financial Personal Plan" not in text or not re.search(
        r"Personal\s*Registered\s*Savings\s*Plan\s*\(RRSP\)", text
    ):
        raise ValueError(f"{filename} does not look like a Manulife RRSP statement")
    customer_match = re.search(
        r"(?:Your\s*customer\s*number\s*:?[\s]*|customer\s*number\s*:?[\s]*)(\d+)",
        text,
        re.IGNORECASE,
    )
    period_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s*"
        r"(\d{1,2}),\s*(\d{4})\s*to\s*"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s*"
        r"(\d{1,2}),\s*(\d{4})",
        text,
    )
    if not customer_match or not period_match:
        raise ValueError(f"Could not read the Manulife RRSP identity or period in {filename}")
    start_date = date(
        int(period_match.group(3)),
        datetime.strptime(period_match.group(1), "%B").month,
        int(period_match.group(2)),
    ).isoformat()
    end_date = date(
        int(period_match.group(6)),
        datetime.strptime(period_match.group(4), "%B").month,
        int(period_match.group(5)),
    ).isoformat()
    section = re.search(
        r"(?:What\s*happened\s*in\s*your\s*plan\s*this\s*period|happened\s*What\s*this\s*period\s*in\s*your\s*plan)(.*?)(?:Your\s*plan\s*assets\s*are\s*not\s*locked\s*in\.|How\s*your\s*investments\s*are\s*performing)",
        text,
        re.S | re.IGNORECASE,
    )
    if not section:
        raise ValueError(f"Could not read the Manulife RRSP period totals in {filename}")
    body = section.group(1)

    def value_after(label: str) -> float | None:
        label_pattern = r"\s*".join(re.escape(part) for part in label.split())
        match = re.search(rf"{label_pattern}\s*\$([\d,]+\.\d{{2}})", body, re.IGNORECASE)
        return _money(match.group(1)) if match else None

    opening = value_after("Opening value")
    closing_match = re.search(
        r"Value\s*on\s*(?:[A-Za-z]+\s*\d{1,2},\s*\d{4})\s*\$([\d,]+\.\d{2})", body
    )
    closing = _money(closing_match.group(1)) if closing_match else None
    money_in = value_after("Plus money that went in")
    money_out = value_after("Less money that came out")
    if money_in is None:
        contributions_section = re.search(
            r"Plus\s*contributions\s*for\s*:(.*?)(?:Plus\s*savings\s*bonus)",
            body,
            re.S | re.IGNORECASE,
        )
        money_in = 0.0
        if contributions_section:
            for line in contributions_section.group(1).splitlines():
                amounts = re.findall(r"\$([\d,]+\.\d{2})", line)
                if amounts:
                    money_in += _money(amounts[-1])
    if money_out is None:
        money_out = 0.0
    bonus = value_after("Plus savings bonus")
    growth = value_after("Plus growth in value")
    if opening is None or closing is None:
        raise ValueError(f"Could not read the Manulife RRSP balances in {filename}")

    rows: list[dict[str, object]] = []
    running = opening
    if money_in:
        running += money_in
        rows.append(
            {
                "date": end_date,
                "amount": money_in,
                "balance": round(running, 2),
                "description": "Manulife contributions",
                "category": "Contribution",
                "transaction_type": "contribution",
            }
        )
    if money_out:
        running -= money_out
        rows.append(
            {
                "date": end_date,
                "amount": -money_out,
                "balance": round(running, 2),
                "description": "Manulife withdrawals",
                "category": "Withdrawal",
                "transaction_type": "withdrawal",
            }
        )
    if bonus:
        running += bonus
        rows.append(
            {
                "date": end_date,
                "amount": bonus,
                "balance": round(running, 2),
                "description": "Manulife savings bonus",
                "category": "Interest",
                "transaction_type": "interest",
            }
        )
    if growth:
        running += growth
        rows.append(
            {
                "date": end_date,
                "amount": growth,
                "balance": round(running, 2),
                "description": "Manulife investment growth",
                "category": "Growth",
                "transaction_type": "growth",
            }
        )
    if round(running, 2) != round(closing, 2):
        raise ValueError(f"Manulife period totals do not reconcile in {filename}")
    holdings = _parse_holdings(text, end_date)
    return {
        "account_number": customer_match.group(1),
        "statement_start": start_date,
        "statement_end": end_date,
        "opening_value": opening,
        "closing_value": closing,
        "rows": rows,
        "holdings": holdings,
    }


def is_manulife_rrsp_pdf(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:3])
        return "Manulife Financial Personal Plan" in text and bool(
            re.search(r"Personal\s*Registered\s*Savings\s*Plan\s*\(RRSP\)", text)
        )
    except Exception:
        return False
