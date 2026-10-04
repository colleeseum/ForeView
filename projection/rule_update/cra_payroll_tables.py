"""Extract annual tax-calculation inputs from official CRA payroll tables."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .errors import RuleSourceFormatError
from .html_document import OfficialHtmlDocument
from .parsing import decimal_value


def ontario_payroll_table_url(tax_year: int, *, current_year: int | None = None) -> str:
    reference_year = current_year if current_year is not None else date.today().year
    if tax_year == reference_year:
        return (
            "https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/"
            "t4032-payroll-deductions-tables/t4032on-jan/"
            "t4032on-january-general-information.html?wbdisable=true"
        )
    return (
        "https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/"
        "t4032-payroll-deductions-tables-previous-years/"
        f"t4032on-january-{tax_year}/t4032on-january-general-information.html"
        "?wbdisable=true"
    )


def manitoba_payroll_table_url(tax_year: int, *, current_year: int | None = None) -> str:
    reference_year = current_year if current_year is not None else date.today().year
    if tax_year == reference_year:
        return (
            "https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/"
            "t4032-payroll-deductions-tables/t4032mb-jan/"
            "t4032mb-january-general-information.html?wbdisable=true"
        )
    edition = "july" if tax_year == 2025 else "january"
    return (
        "https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/"
        "t4032-payroll-deductions-tables-previous-years/"
        f"t4032mb-{edition}-{tax_year}/t4032mb-{edition}-general-information.html"
        "?wbdisable=true"
    )


MANITOBA_PHASEOUT_URL = (
    "https://www.canada.ca/en/revenue-agency/services/forms-publications/payroll/"
    "t4032-payroll-deductions-tables-previous-years/t4032mb-january-2025/"
    "t4032mb-january-general-information.html?wbdisable=true"
)


def federal_basic_personal_amounts(content: bytes, source_id: str) -> tuple[Decimal, Decimal]:
    rows = OfficialHtmlDocument(content).table_rows
    for index, row in enumerate(rows[:-1]):
        if row and row[0].casefold().startswith("maximum basic personal amount"):
            values = rows[index + 1]
            if len(values) >= 2:
                return decimal_value(values[0]), decimal_value(values[1])
    raise RuleSourceFormatError(f"Could not find federal basic personal amounts in {source_id}")


def canada_employment_amount(content: bytes, source_id: str) -> Decimal:
    text = OfficialHtmlDocument(content).text
    match = re.search(
        r"Canada Employment Amount.*?lesser of:\s*\$?([\d,]+)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        match = re.search(
            r"Canada Employment Amount.*?annual maximum\s*\$([\d,]+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if match is None:
        raise RuleSourceFormatError(f"Could not find Canada employment amount in {source_id}")
    return decimal_value(match.group(1))


def cpp_component_rates(content: bytes, source_id: str) -> tuple[Decimal, Decimal]:
    text = OfficialHtmlDocument(content).text
    base = re.search(r"CPP base contribution(?:\s+[\d,.]+){3}\s+(0\.\d+)", text, flags=re.I)
    additional = re.search(
        r"First additional CPP contribution(?:\s+[\d,.]+){3}\s+(0\.\d+)",
        text,
        flags=re.I,
    )
    if base is None or additional is None:
        raise RuleSourceFormatError(f"Could not find CPP component rates in {source_id}")
    return Decimal(base.group(1)), Decimal(additional.group(1))


def ontario_tax_parameters(
    content: bytes, source_id: str
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    document = OfficialHtmlDocument(content)
    text = document.text
    basic_amount = _ontario_basic_personal_amount(document, source_id)
    surtax_section = _section(text, "Ontario’s surtax is", "Tax reduction", source_id)
    thresholds = [
        amount
        for value in re.findall(r"\$([\d,]+)", surtax_section)
        if (amount := decimal_value(value)) > 0
    ]
    rates = [
        rate
        for value in re.findall(r"(\d+)%", surtax_section)
        if (rate := Decimal(value) / Decimal("100")) > 0
    ]
    unique_thresholds = tuple(sorted(set(thresholds)))
    unique_rates = tuple(dict.fromkeys(rates))
    if len(unique_thresholds) < 2 or len(unique_rates) < 2:
        raise RuleSourceFormatError(f"Could not find Ontario surtax tiers in {source_id}")
    return (
        basic_amount,
        unique_thresholds[0],
        unique_rates[0],
        unique_thresholds[1],
        unique_rates[1],
    )


def manitoba_tax_parameters(
    annual_content: bytes, phaseout_content: bytes, source_id: str
) -> tuple[Decimal, Decimal, Decimal]:
    annual_text = OfficialHtmlDocument(annual_content).text
    amount_match = re.search(
        r"(?:BPAMB for \d{4} is|maximum BPAMB for \d{4} will remain at)\s+\$([\d,]+)",
        annual_text,
        flags=re.IGNORECASE,
    )
    phaseout_match = re.search(
        r"net income\s+between\s+\$([\d,]+)\s+and\s+\$([\d,]+)",
        OfficialHtmlDocument(phaseout_content).text,
        flags=re.IGNORECASE,
    )
    if amount_match is None or phaseout_match is None:
        raise RuleSourceFormatError(f"Could not find Manitoba BPA phaseout inputs in {source_id}")
    return (
        decimal_value(amount_match.group(1)),
        decimal_value(phaseout_match.group(1)),
        decimal_value(phaseout_match.group(2)),
    )


def _ontario_basic_personal_amount(document: OfficialHtmlDocument, source_id: str) -> Decimal:
    for index, row in enumerate(document.table_rows[:-1]):
        if row and row[0].casefold().startswith("basic personal amount"):
            values = document.table_rows[index + 1]
            if values:
                return decimal_value(values[0])
    match = re.search(
        r"Ontario non.refundable (?:basic )?personal tax credit is\s+\$([\d,]+)",
        document.text,
        flags=re.IGNORECASE,
    )
    if match is not None:
        return decimal_value(match.group(1))
    raise RuleSourceFormatError(f"Could not find Ontario basic personal amount in {source_id}")


def _section(text: str, start: str, end: str, source_id: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start))
    if start_index < 0 or end_index < 0:
        raise RuleSourceFormatError(f"Could not find Ontario surtax section in {source_id}")
    return text[start_index:end_index]
