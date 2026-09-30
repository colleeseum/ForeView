from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from domain.parsed_tax_assessment import ParsedTaxAssessment
from domain.parsed_tax_value import ParsedTaxValue


class RevenuQuebecNoticeParser:
    """Extract assessed Quebec tax totals from a Revenu Québec notice."""

    @staticmethod
    def detects(content: bytes) -> bool:
        try:
            text = RevenuQuebecNoticeParser._text(content)
        except (OSError, ValueError, PdfminerException):
            return False
        return "Notice of assessment" in text and "Revenu Québec" in text

    def parse(self, content: bytes) -> ParsedTaxAssessment:
        text = self._text(content)
        year = int(
            self._required(text, r"Notice of assessment\s+(\d{4}) taxation year", "tax year")
        )
        issued = (
            datetime.strptime(
                self._required(
                    text, r"Date of notice:\s+([A-Z][a-z]+ \d{1,2}, \d{4})", "issue date"
                ),
                "%B %d, %Y",
            )
            .date()
            .isoformat()
        )
        balance = self._amount(
            self._required(
                text,
                r"Balance due for this notice of assessment\s*=\s*\$?\s*([\d,]+\.\d{2})",
                "balance",
            )
        )
        return ParsedTaxAssessment(
            tax_year=year,
            jurisdiction="CA-QC",
            issued_on=issued,
            taxpayer_name=self._taxpayer_name(text),
            total_income=self._line(text, "199", "Total income"),
            net_income=self._line(text, "275", "Net income"),
            taxable_income=self._line(text, "299", "Taxable income"),
            net_tax=self._line(text, "432", "Income tax"),
            additional_contributions=self._line(text, "439", "QPIP premium", multiline=True),
            tax_withheld=self._line(text, "454", "Transferable portion", multiline=True),
            balance=balance,
            tax_values=self._tax_values(text, year),
        )

    def _tax_values(self, text: str, tax_year: int) -> tuple[ParsedTaxValue, ...]:
        values: list[ParsedTaxValue] = []
        for line, concept, description in (
            ("96", "cpp_qpp_contributions", "CPP or QPP contributions"),
            ("101", "employment_income", "Employment income"),
            ("107", "other_employment_income", "Other employment income"),
            ("114", "oas_income", "Old Age Security pension"),
            ("119", "cpp_qpp_benefits", "CPP or QPP benefits"),
            ("122", "other_pension_income", "Other pension income"),
            ("130", "interest_investment_income", "Interest and other investment income"),
            ("136", "taxable_canadian_dividends", "Taxable Canadian dividends"),
            ("139", "taxable_capital_gains", "Taxable capital gains"),
            ("164", "net_business_income", "Net business income"),
            ("199", "total_income", "Total income"),
            ("201", "worker_deduction", "Deduction for workers"),
            ("214", "rrsp_deduction", "RRSP or PRPP deduction"),
            ("248", "enhanced_contribution_deduction", "Enhanced payroll contribution deduction"),
            ("275", "net_income", "Net income"),
            ("299", "taxable_income", "Taxable income"),
            ("350", "basic_personal_amount", "Basic personal amount"),
            ("377", "personal_tax_credit_base", "Amounts used for personal tax credits"),
            ("377.1", "personal_tax_credit", "Personal tax credit"),
            ("399", "non_refundable_tax_credits", "Non-refundable tax credits"),
            ("401", "tax_on_taxable_income", "Income tax on taxable income"),
            ("406", "non_refundable_tax_credit_amount", "Non-refundable tax credit amount"),
            ("432", "quebec_income_tax", "Quebec income tax"),
            ("439", "qpip_additional_premium", "Additional QPIP premium"),
            ("450", "income_tax_and_contributions", "Income tax and contributions"),
            ("454", "tax_withheld_transferred", "Tax withheld transferred from another province"),
            ("479", "balance_due", "Balance due"),
        ):
            amounts = self._line_amounts(text, line)
            if amounts:
                values.append(
                    ParsedTaxValue(
                        concept=concept,
                        description=description,
                        reported_amount=amounts[0] if len(amounts) > 1 else None,
                        determined_amount=amounts[-1],
                        line_code=line,
                        effective_year=tax_year,
                    )
                )
        balance_interest = self._optional_amount(
            text, r"Interest on the balance\s*\+?\s*\$?\s*([\d,]+\.\d{2})"
        )
        if balance_interest is not None:
            values.append(
                ParsedTaxValue(
                    "assessment_balance_interest",
                    "Interest on the assessed balance",
                    None,
                    balance_interest,
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
            raise ValueError(f"Revenu Québec notice {label} was not found")
        return match.group(1)

    def _line(
        self, text: str, number: str, description: str, *, multiline: bool = False
    ) -> Decimal:
        lines = text.splitlines()
        matching = next(
            (
                index
                for index, line in enumerate(lines)
                if re.match(rf"^{number}\s+{re.escape(description)}", line, re.IGNORECASE)
            ),
            None,
        )
        if matching is None:
            raise ValueError(f"Revenu Québec notice line {number} was not found")
        selected = lines[matching]
        if multiline and matching + 1 < len(lines):
            selected += " " + lines[matching + 1]
        values = re.findall(r"(?<!\d)([\d,]+\.\d{2})(?!\d)", selected)
        if not values:
            raise ValueError(f"Revenu Québec notice line {number} amount was not found")
        return self._amount(values[-1])

    def _line_amounts(self, text: str, number: str) -> tuple[Decimal, ...]:
        lines = text.splitlines()
        matching = next(
            (
                index
                for index, line in enumerate(lines)
                if re.match(rf"^{re.escape(number)}(?:\s|$)", line)
            ),
            None,
        )
        if matching is None:
            return ()
        selected = lines[matching]
        for following in lines[matching + 1 : matching + 3]:
            if re.match(r"^\d+(?:\.\d+)?(?:\s|$)", following):
                break
            selected += " " + following
        return tuple(
            self._amount(raw) for raw in re.findall(r"(?<!\d)([\d,]+\.\d{2})(?!\d)", selected)
        )

    def _optional_amount(self, text: str, pattern: str) -> Decimal | None:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        return self._amount(match.group(1)) if match else None

    @staticmethod
    def _taxpayer_name(text: str) -> str | None:
        match = re.search(
            r"First name and last name[^\n]*\n\s*([A-Za-zÀ-ÿ .'-]+?)\s+[A-Z][a-z]+ \d{1,2}, \d{4}",
            text,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _amount(raw: str) -> Decimal:
        return Decimal(raw.replace(",", "").replace(" ", ""))
