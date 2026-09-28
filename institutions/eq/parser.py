"""Parser for EQ monthly PDF transaction statements."""

import re
from collections.abc import Iterable
from datetime import datetime

_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DATE_LINE = re.compile(rf"^({_MONTHS})\s+(\d{{1,2}})\s+(.+)$")
_MONEY = re.compile(r"\$[\d,]+\.\d{2}")
_STATEMENT_YEAR = re.compile(r"^[A-Za-z]+\s+(\d{4})\s+Statement\s*$", re.MULTILINE)
_ACCOUNT_NUMBER = re.compile(r"Account\s*#\s*([\d -]+)", re.IGNORECASE)


def parse_eq_pdf_transactions(
    page_texts: Iterable[str], filename: str = "statement.pdf"
) -> tuple[str | None, list[dict[str, object]]]:
    """Parse EQ transaction rows while retaining the source row details."""
    pages = list(page_texts)
    full_text = "\n".join(pages)
    year_match = _STATEMENT_YEAR.search(full_text)
    if not year_match:
        raise ValueError(f"{filename} does not look like an EQ monthly statement")
    year = int(year_match.group(1))
    account_match = _ACCOUNT_NUMBER.search(full_text)
    statement_account = re.sub(r"\D", "", account_match.group(1)) if account_match else None
    rows: list[dict[str, object]] = []
    unparsed: list[str] = []
    for page_number, page_text in enumerate(pages, start=1):
        for line_number, line in enumerate(page_text.splitlines(), start=1):
            match = _DATE_LINE.match(line.strip())
            if not match:
                continue
            money = list(_MONEY.finditer(line))
            if len(money) < 2:
                unparsed.append(line.strip())
                continue
            amount_match, balance_match = money[-2], money[-1]
            prefix = line[: amount_match.start()]
            amount = float(amount_match.group().replace("$", "").replace(",", ""))
            if re.search(r"-\s*$", prefix):
                amount = -amount
            description = line[match.start(3) : amount_match.start()]
            description = re.sub(r"-\s*$", "", description).strip()
            try:
                transaction_date = (
                    datetime.strptime(f"{match.group(1)} {match.group(2)} {year}", "%b %d %Y")
                    .date()
                    .isoformat()
                )
            except ValueError:
                unparsed.append(line.strip())
                continue
            rows.append(
                {
                    "page": page_number,
                    "line": line_number,
                    "date": transaction_date,
                    "amount": amount,
                    "description": description,
                    "balance": float(balance_match.group().replace("$", "").replace(",", "")),
                    "raw_line": line.strip(),
                }
            )
    if unparsed:
        raise ValueError(f"Could not parse {len(unparsed)} transaction row(s) in {filename}")
    if not rows:
        raise ValueError(f"No transaction rows found in {filename}")
    return statement_account, rows
