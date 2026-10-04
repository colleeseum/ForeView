# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Parser for Achieva GIC transaction-history PDFs."""

import io
import re
from collections.abc import Iterable
from datetime import datetime

import pdfplumber


def _money(value: object) -> float:
    return float(str(value).replace(",", ""))


def parse_achieva_gic_pdf(
    page_texts: Iterable[str], filename: str = "statement.pdf"
) -> dict[str, object]:
    text = "\n".join(page_texts).replace("\xa0", " ")
    if "Transactions" not in text or "System Generated Entry" not in text:
        raise ValueError(f"{filename} does not look like an Achieva GIC statement")
    title_match = re.search(r"Transactions\s*\n([^\n]+)\s*\n\$([\d,]+\.\d{2})", text)
    if not title_match:
        raise ValueError(f"Could not read the Achieva GIC title in {filename}")
    date_line = re.compile(
        r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})$", re.MULTILINE
    )
    blocks = list(date_line.finditer(text, re.MULTILINE))
    rows: list[dict[str, object]] = []
    for index, match in enumerate(blocks):
        block = text[
            match.end() : blocks[index + 1].start() if index + 1 < len(blocks) else len(text)
        ]
        amounts = re.findall(r"\$([\d,]+\.\d{2})", block)
        if len(amounts) < 2:
            continue
        description = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if "interest" in description.lower():
            transaction_type, category, clean_description = "interest", "Interest", "GIC interest"
        elif "Tax Sheltered TFSA Transfer" in description:
            transaction_type, category, clean_description = (
                "transfer",
                "Transfer",
                "TFSA transfer into GIC",
            )
        else:
            continue
        transaction_date = (
            datetime.strptime(f"{match.group(1)} {match.group(2)} {match.group(3)}", "%b %d %Y")
            .date()
            .isoformat()
        )
        rows.append(
            {
                "date": transaction_date,
                "amount": _money(amounts[0]),
                "balance": _money(amounts[1]),
                "description": clean_description,
                "category": category,
                "transaction_type": transaction_type,
            }
        )
    if not rows:
        raise ValueError(f"No Achieva GIC transactions found in {filename}")
    return {
        "name": title_match.group(1).strip(),
        "closing_value": _money(title_match.group(2)),
        "rows": rows,
        "statement_date": max(str(row["date"]) for row in rows),
        "principal": next(
            (row["amount"] for row in rows if row["transaction_type"] == "transfer"), None
        ),
        "start_date": min(str(row["date"]) for row in rows),
    }


def is_achieva_gic_pdf(content: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:1])
        return "Transactions" in text and "System Generated Entry" in text and "TFSA GIC" in text
    except Exception:
        return False
