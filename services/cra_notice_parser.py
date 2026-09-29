from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from domain.parsed_tax_assessment import ParsedTaxAssessment
from domain.parsed_tax_value import ParsedTaxValue


class CraNoticeParser:
    """Extract assessed federal totals and RRSP room from a CRA notice."""

    @staticmethod
    def detects(content: bytes) -> bool:
        try:
            text = CraNoticeParser._text(content)
        except (OSError, ValueError, PdfminerException):
            return False
        return "Notice of assessment" in text and "Net federal tax" in text

    def parse(self, content: bytes) -> ParsedTaxAssessment:
        text = self._text(content)
        year = int(self._required(text, r"Tax year\s+(\d{4})", "tax year"))
        issued = (
            datetime.strptime(
                self._required(text, r"Date issued\s+([A-Z][a-z]+ \d{1,2}, \d{4})", "issue date"),
                "%B %d, %Y",
            )
            .date()
            .isoformat()
        )
        room_year = self._optional_int(text, r"Your (\d{4}) RRSP deduction limit")
        balance_value = self._required(
            text, r"Balance from this assessment\s+([\d,]+(?:\.\d{2})?)\s*(CR|DR)?", "balance"
        )
        balance_match = re.search(
            r"Balance from this assessment\s+([\d,]+(?:\.\d{2})?)\s*(CR|DR)?", text
        )
        balance = self._amount(balance_value)
        if balance_match and balance_match.group(2) == "CR":
            balance = -balance
        return ParsedTaxAssessment(
            tax_year=year,
            jurisdiction="CA",
            issued_on=issued,
            taxpayer_name=self._taxpayer_name(text),
            total_income=self._line(text, "15000", "Total income"),
            net_income=self._line(text, "23600", "Net income"),
            taxable_income=self._line(text, "26000", "Taxable income"),
            net_tax=self._line(text, "42000", "Net federal tax"),
            additional_contributions=Decimal("0"),
            tax_withheld=self._line(text, "43700", "Total income tax deducted"),
            balance=balance,
            rrsp_effective_year=room_year,
            rrsp_deduction_limit=self._optional_amount(
                text,
                rf"Equals:\s*RRSP deduction limit for\s*{room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
            ),
            rrsp_unused_deduction_room=self._optional_amount(
                text, rf"unused RRSP deduction room at the end of {year}\s+([\d,]+)"
            ),
            rrsp_new_room=self._optional_amount(
                text, rf"Additional RRSP deduction limit you earned in {year}.*?\s+([\d,]+)\s*$"
            ),
            rrsp_unused_contributions=self._optional_amount(
                text,
                rf"Unused RRSP contributions previously reported and available to deduct for {room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
            ),
            rrsp_available_room=self._optional_amount(
                text,
                rf"available RRSP contribution room for\s*{room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
            ),
            tax_values=self._tax_values(text, year, room_year),
        )

    def _tax_values(
        self, text: str, tax_year: int, room_year: int | None
    ) -> tuple[ParsedTaxValue, ...]:
        values: list[ParsedTaxValue] = []
        for line, concept, description in (
            ("15000", "total_income", "Total income"),
            ("23600", "net_income", "Net income"),
            ("26000", "taxable_income", "Taxable income"),
            ("35000", "non_refundable_tax_credits", "Non-refundable tax credits"),
            ("42000", "net_federal_tax", "Net federal tax"),
            ("43500", "total_payable", "Total payable"),
            ("43700", "income_tax_deducted", "Income tax deducted"),
            ("44000", "refundable_quebec_abatement", "Refundable Quebec abatement"),
            ("48200", "total_credits", "Total credits"),
        ):
            amount = self._optional_line(text, line, description)
            if amount is not None:
                values.append(
                    ParsedTaxValue(concept, description, None, amount, line, tax_year)
                )
        for concept, description, pattern, effective_year in (
            (
                "deductions_from_total_income",
                "Deductions from total income",
                r"Deductions from total income\s+([\d,]+(?:\.\d{2})?)",
                tax_year,
            ),
            (
                "tax_withheld_transferred_to_quebec",
                "Income tax withheld transferred to Quebec",
                r"transferred to Quebec \$([\d,]+(?:\.\d{2})?)",
                tax_year,
            ),
            (
                "canada_training_credit_limit",
                "Canada training credit limit",
                r"Canada training credit limit for next year is \$([\d,]+(?:\.\d{2})?)",
                tax_year + 1,
            ),
            (
                "rrsp_prior_deduction_limit",
                "RRSP deduction limit for the tax year",
                rf"RRSP deduction limit for {tax_year}\s+([\d,]+)",
                tax_year,
            ),
            (
                "rrsp_employer_prpp_contributions",
                "Employer PRPP contributions",
                rf"Employer's PRPP contributions for {tax_year}\s+([\d,]+)",
                tax_year,
            ),
            (
                "rrsp_contributions_deducted",
                "Allowable RRSP contributions deducted",
                rf"Allowable RRSP contributions deducted for {tax_year}\s+([\d,]+)",
                tax_year,
            ),
            (
                "rrsp_unused_deduction_room",
                "Unused RRSP deduction room",
                rf"unused RRSP deduction room at the end of {tax_year}\s+([\d,]+)",
                tax_year,
            ),
            (
                "rrsp_earned_room_before_adjustments",
                "RRSP room from earned income before adjustments",
                rf"18% of {tax_year} earned income.*?\s+([\d,]+)\s*$",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_pension_adjustment",
                "Pension adjustment",
                rf"{tax_year} pension adjustment \(PA\)\s+([\d,]+)",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_prescribed_amount",
                "Prescribed amount for connected persons",
                rf"{tax_year} prescribed amount for connected persons\s+([\d,]+)",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_additional_deduction_limit",
                "Additional RRSP deduction limit earned",
                rf"Additional RRSP deduction limit you earned in {tax_year}.*?\s+([\d,]+)\s*$",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_net_past_service_pension_adjustment",
                "Net past service pension adjustment",
                rf"{room_year} net past service pension adjustment \(PSPA\)\s+([\d,]+)"
                if room_year
                else r"(?!)",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_pension_adjustment_reversal",
                "Pension adjustment reversal",
                r"pension adjustment reversal \(PAR\)\s+([\d,]+)",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_deduction_limit",
                "RRSP deduction limit",
                rf"Equals:\s*RRSP deduction limit for\s*{room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_unused_contributions",
                "Unused RRSP contributions available to deduct",
                rf"Unused RRSP contributions previously reported and available to deduct for {room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
                room_year or tax_year + 1,
            ),
            (
                "rrsp_available_contribution_room",
                "Available RRSP contribution room",
                rf"available RRSP contribution room for\s*{room_year}\s+([\d,]+)"
                if room_year
                else r"(?!)",
                room_year or tax_year + 1,
            ),
        ):
            amount = self._optional_amount(text, pattern)
            if amount is not None:
                values.append(
                    ParsedTaxValue(
                        concept,
                        description,
                        None,
                        amount,
                        effective_year=effective_year,
                    )
                )
        balance_match = re.search(
            r"Balance from this assessment\s+([\d,]+(?:\.\d{2})?)\s*(CR|DR)?", text
        )
        if balance_match:
            amount = self._amount(balance_match.group(1))
            if balance_match.group(2) == "CR":
                amount = -amount
            values.append(
                ParsedTaxValue(
                    "assessment_balance",
                    "Balance from the assessment",
                    None,
                    amount,
                    effective_year=tax_year,
                )
            )
        return tuple(values)

    @staticmethod
    def _text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    @staticmethod
    def _required(text: str, pattern: str, label: str) -> str:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if not match:
            raise ValueError(f"CRA notice {label} was not found")
        return match.group(1)

    def _line(self, text: str, number: str, description: str) -> Decimal:
        raw = self._required(
            text,
            rf"^{number}\s+{re.escape(description)}\s+([\d,]+(?:\.\d{{2}})?)",
            f"line {number}",
        )
        return self._amount(raw)

    def _optional_line(self, text: str, number: str, description: str) -> Decimal | None:
        try:
            return self._line(text, number, description)
        except ValueError:
            return None

    @staticmethod
    def _taxpayer_name(text: str) -> str | None:
        match = re.search(r"(?m)^([A-Z][A-Z .'-]+)\n\d+\s+[A-Z]", text)
        return match.group(1).title() if match else None

    @staticmethod
    def _amount(raw: str) -> Decimal:
        value = raw.replace(",", "").replace(" ", "")
        negative = value.startswith("(") and value.endswith(")")
        amount = Decimal(value.strip("()"))
        return -amount if negative else amount

    def _optional_amount(self, text: str, pattern: str) -> Decimal | None:
        matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        return self._amount(matches[-1]) if matches else None

    @staticmethod
    def _optional_int(text: str, pattern: str) -> int | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return int(match.group(1)) if match else None
