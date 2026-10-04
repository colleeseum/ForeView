# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import io
import re
from decimal import Decimal
from typing import Any

import pdfplumber

from domain.parsed_tax_value import ParsedTaxValue
from domain.parsed_ufile_tax_return import ParsedUFileTaxReturn


class UFileTaxReturnParser:
    """Read one taxpayer's factual annual values from a UFile PDF package."""

    _SUMMARY = re.compile(r"Tax return Summary\s+for (\d{4}) taxation year", re.I)
    _NUMBER = re.compile(r"^\(?[\d,]+(?:\.\d{2})?\)?$")
    _USEFUL_T1_LINES = (
        ("10100", "employment_income", "Employment income"),
        ("10400", "other_employment_income", "Other employment income"),
        ("11300", "oas_income", "Old Age Security pension"),
        ("11400", "cpp_qpp_benefits", "CPP or QPP benefits"),
        ("11500", "other_pension_income", "Other pensions and superannuation"),
        ("11600", "elected_split_pension", "Elected split-pension amount"),
        ("11900", "employment_insurance_benefits", "Employment Insurance benefits"),
        ("12000", "taxable_canadian_dividends", "Taxable Canadian dividends"),
        ("12100", "interest_investment_income", "Interest and other investment income"),
        ("12200", "limited_partnership_income", "Limited partnership income"),
        ("12500", "rdsp_income", "Registered disability savings plan income"),
        ("12600", "net_rental_income", "Net rental income"),
        ("12700", "taxable_capital_gains", "Taxable capital gains"),
        ("12800", "support_payments_received", "Taxable support payments received"),
        ("12900", "rrsp_income", "RRSP income"),
        ("12905", "fhsa_income", "Taxable FHSA income"),
        ("13000", "other_taxable_income", "Other taxable income"),
        ("13010", "scholarship_income", "Taxable scholarship income"),
        ("13500", "business_income", "Net business income"),
        ("13700", "professional_income", "Net professional income"),
        ("13900", "commission_income", "Net commission income"),
        ("14100", "farming_income", "Net farming income"),
        ("14300", "fishing_income", "Net fishing income"),
        ("14400", "workers_compensation", "Workers' compensation benefits"),
        ("14500", "social_assistance", "Social assistance payments"),
        ("14600", "federal_supplements", "Net federal supplements"),
        ("14700", "other_benefits_total", "Other benefits total"),
        ("15000", "total_income", "Total income"),
        ("20700", "registered_pension_plan_deduction", "Registered pension plan deduction"),
        ("20800", "rrsp_deduction", "RRSP deduction"),
        ("20805", "fhsa_deduction", "FHSA deduction"),
        ("21000", "pension_split_deduction", "Pension split deduction"),
        ("21200", "union_professional_dues", "Union and professional dues"),
        ("21400", "child_care_expenses", "Child care expenses"),
        ("21900", "moving_expenses", "Moving expenses"),
        ("22000", "support_payments_made", "Support payments made"),
        ("22100", "carrying_charges_interest", "Carrying charges and interest expenses"),
        ("22200", "self_employed_cpp_qpp_deduction", "Self-employed CPP or QPP deduction"),
        ("22215", "enhanced_cpp_qpp_deduction", "Enhanced CPP or QPP deduction"),
        ("22900", "other_employment_expenses", "Other employment expenses"),
        ("23200", "other_deductions", "Other deductions"),
        ("23300", "total_income_deductions", "Total deductions from income"),
        ("23400", "net_income_before_adjustments", "Net income before adjustments"),
        ("23500", "social_benefits_repayment", "Social benefits repayment"),
        ("23600", "net_income", "Net income"),
        ("25700", "total_taxable_income_deductions", "Total deductions from taxable income"),
        ("26000", "taxable_income", "Taxable income"),
        ("30000", "basic_personal_amount", "Basic personal amount"),
        ("30800", "base_cpp_qpp_contributions", "Base CPP or QPP contributions"),
        ("31200", "employment_insurance_premiums", "Employment Insurance premiums"),
        ("31210", "qpip_premiums", "QPIP premiums"),
        ("35000", "non_refundable_tax_credits", "Non-refundable tax credits"),
        ("42000", "net_federal_tax", "Net federal tax"),
        ("43500", "total_payable", "Total payable"),
        ("43700", "income_tax_deducted", "Income tax deducted"),
        ("43800", "tax_transferred_to_quebec", "Income tax transferred to Quebec"),
        ("44000", "refundable_quebec_abatement", "Refundable Quebec abatement"),
        ("45000", "employment_insurance_overpayment", "Employment Insurance overpayment"),
        ("48200", "total_credits", "Total credits"),
        ("48400", "refund", "Refund"),
        ("48500", "balance_owing", "Balance owing"),
    )

    @staticmethod
    def detects(content: bytes) -> bool:
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        except (OSError, ValueError):
            return False
        return bool(re.search(r"Tax return Summary|UFile", text, re.IGNORECASE))

    def parse(self, content: bytes) -> ParsedUFileTaxReturn:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = list(pdf.pages)
            summary_index, tax_year = self._find_individual_summary(pages)
            federal_page = pages[summary_index]
            taxpayer_name = self._taxpayer_name(pages, summary_index, tax_year)
            quebec_page = pages[summary_index + 1] if summary_index + 1 < len(pages) else None
            if quebec_page is None or "Quebec return" not in (quebec_page.extract_text() or ""):
                raise ValueError("The UFile Quebec summary page was not found")

            employment_income = self._required_line(federal_page, "10100")
            other_employment_income = self._optional_line(federal_page, "10400")
            base_cpp_qpp = self._required_line(federal_page, "30800")
            enhanced_cpp_qpp = self._optional_line(federal_page, "22215")
            rrsp_contribution = self._find_rrsp_contribution(pages)
            tax_values = tuple(
                ParsedTaxValue(
                    concept=concept,
                    description=description,
                    reported_amount=amount,
                    line_code=line_number,
                    effective_year=tax_year,
                )
                for line_number, concept, description in self._USEFUL_T1_LINES
                if (amount := self._line_amount(federal_page, line_number)) is not None
            )

            return ParsedUFileTaxReturn(
                tax_year=tax_year,
                employment_income=employment_income,
                other_employment_income=other_employment_income,
                cpp_qpp=base_cpp_qpp + enhanced_cpp_qpp,
                ei=self._optional_line(federal_page, "31200"),
                qpip=self._optional_line(federal_page, "31210"),
                rrsp_contribution=rrsp_contribution,
                rrsp_deduction=self._optional_line(federal_page, "20800"),
                federal_tax=self._required_line(federal_page, "42000"),
                provincial_tax=self._required_line(quebec_page, "432"),
                province_of_residence="QC",
                payroll_plan=self._payroll_plan(quebec_page.extract_text() or ""),
                taxpayer_name=taxpayer_name,
                tax_values=tax_values,
            )

    @staticmethod
    def _payroll_plan(quebec_text: str) -> str | None:
        if re.search(r"\bCPP contribution\b", quebec_text, re.IGNORECASE):
            return "CPP"
        if re.search(r"\bQPP contribution\b", quebec_text, re.IGNORECASE):
            return "QPP"
        return None

    def _find_individual_summary(self, pages: list[Any]) -> tuple[int, int]:
        for index, page in enumerate(pages):
            text = page.extract_text() or ""
            match = self._SUMMARY.search(text)
            if match and "Combined" not in text[:200]:
                return index, int(match.group(1))
        raise ValueError("This PDF does not contain an individual UFile tax return summary")

    @staticmethod
    def _taxpayer_name(pages: list[Any], summary_index: int, tax_year: int) -> str | None:
        """Read an explicitly labelled taxpayer name when UFile includes one.

        The name is deliberately optional. UFile layouts can omit it from the
        summary pages, and guessing from an arbitrary line could identify the
        wrong person. The UI asks for manual verification when it is absent.
        """
        text = "\n".join((page.extract_text() or "") for page in pages[summary_index:])
        patterns = (
            r"^(?:Taxpayer|Taxpayer name|Your name)\s*:\s*(.+?)\s*$",
            r"^(?:Nom|Nom du contribuable)\s*:\s*(.+?)\s*$",
            rf"Tax return for {tax_year} prepared for\s+(.+?)\s+by\s+UFile(?:\.ca)?",
            r"Name:\s*([A-Za-z][A-Za-z .'-]*?)(?=\s+(?:Date of birth|SIN):)",
            r"Name:\s*SIN:\s*([A-Za-z][A-Za-z .'-]*?)(?=\s+\d{3}[- ]\d{3}[- ]\d{3}|\s+\d{9}|$)",
        )
        for pattern in patterns[:2]:
            for line in text.splitlines():
                match = re.match(pattern, line.strip(), re.IGNORECASE)
                if match and match.group(1).strip():
                    return match.group(1).strip()
        for pattern in patterns[2:]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and match.group(1).strip():
                return match.group(1).strip()
        return None

    def _required_line(self, page: Any, line_number: str) -> Decimal:
        value = self._line_amount(page, line_number)
        if value is None:
            raise ValueError(f"UFile line {line_number} was not found")
        return value

    def _optional_line(self, page: Any, line_number: str) -> Decimal:
        return self._line_amount(page, line_number) or Decimal("0.00")

    def _line_amount(
        self, page: Any, line_number: str, *, minimum_x: float = 350
    ) -> Decimal | None:
        words = page.extract_words(use_text_flow=False)
        line_words = [
            word for word in words if word["text"] == line_number and float(word["x0"]) >= minimum_x
        ]
        if not line_words:
            return None
        marker = min(line_words, key=lambda word: float(word["top"]))
        candidates = [
            word
            for word in words
            if abs(float(word["top"]) - float(marker["top"])) < 4
            and float(word["x0"]) >= float(marker["x1"]) - 2
            and self._NUMBER.match(str(word["text"]))
        ]
        if not candidates:
            return None
        return self._amount(str(max(candidates, key=lambda word: float(word["x0"]))["text"]))

    def _find_rrsp_contribution(self, pages: list[Any]) -> Decimal:
        for page in pages:
            value = self._line_amount(page, "24500", minimum_x=0)
            if value is not None:
                return value
        return Decimal("0.00")

    @staticmethod
    def _amount(raw: str) -> Decimal:
        negative = raw.startswith("(") and raw.endswith(")")
        digits = raw.strip("()").replace(",", "")
        if "." not in digits:
            if len(digits) < 3:
                digits = digits.zfill(3)
            digits = f"{digits[:-2]}.{digits[-2:]}"
        value = Decimal(digits)
        return -value if negative else value
