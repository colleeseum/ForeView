# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Official Canadian federal tax and RRSP rule provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from projection.public_rules import (
    IndexingMechanism,
    IndexingMetadata,
    PublicRuleSet,
    RuleParameter,
    RuleStatus,
    RuleUnit,
    TaxBracketSchedule,
)

from .cra_payroll_tables import (
    canada_employment_amount,
    cpp_component_rates,
    federal_basic_personal_amounts,
    ontario_payroll_table_url,
)
from .errors import RuleSourceFormatError
from .html_document import OfficialHtmlDocument
from .parsing import parse_bracket_section, percentage_values, require_year_row
from .source_metadata import rule_source
from .source_retriever import SourceRetriever


class FederalRuleProvider:
    provider_id = "ca.federal"
    jurisdiction = "CA"

    CURRENT_TAX_URL = (
        "https://www.canada.ca/en/revenue-agency/services/tax/individuals/"
        "tax-rates-brackets/current-year.html?wbdisable=true"
    )
    PREVIOUS_TAX_URL = (
        "https://www.canada.ca/en/revenue-agency/services/tax/individuals/"
        "tax-rates-brackets/last-year.html?wbdisable=true"
    )
    HISTORICAL_TAX_URL = (
        "https://www.canada.ca/en/revenue-agency/services/tax/individuals/"
        "tax-rates-brackets/all-years.html?wbdisable=true"
    )
    RRSP_LIMIT_URL = (
        "https://www.canada.ca/en/revenue-agency/services/tax/registered-plans-administrators/"
        "pspa/mp-rrsp-dpsp-tfsa-limits-ympe.html?wbdisable=true"
    )
    RRSP_FORMULA_URL = (
        "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/"
        "rrsps-related-plans/contributing-a-rrsp-prpp/"
        "contributions-affect-your-rrsp-prpp-deduction-limit.html?wbdisable=true"
    )

    @classmethod
    def tax_url(cls, tax_year: int, *, current_year: int | None = None) -> str:
        reference_year = current_year if current_year is not None else date.today().year
        if tax_year == reference_year:
            return cls.CURRENT_TAX_URL
        if tax_year == reference_year - 1:
            return cls.PREVIOUS_TAX_URL
        return cls.HISTORICAL_TAX_URL

    def fetch(self, tax_year: int, retriever: SourceRetriever) -> tuple[PublicRuleSet, ...]:
        tax = retriever.retrieve(
            source_id=f"cra-federal-brackets-{tax_year}",
            title=f"Federal income tax rates and brackets for {tax_year}",
            publisher="Canada Revenue Agency",
            url=self.tax_url(tax_year),
        )
        limits = retriever.retrieve(
            source_id="cra-registered-plan-limits",
            title="Registered plan limits, YMPE and YAMPE",
            publisher="Canada Revenue Agency",
            url=self.RRSP_LIMIT_URL,
        )
        formula = retriever.retrieve(
            source_id="cra-rrsp-deduction-limit-formula",
            title="How RRSP contributions affect the deduction limit",
            publisher="Canada Revenue Agency",
            url=self.RRSP_FORMULA_URL,
        )
        payroll = retriever.retrieve(
            source_id=f"cra-payroll-tables-on-{tax_year}",
            title=f"Federal and Ontario payroll deductions tables for {tax_year}",
            publisher="Canada Revenue Agency",
            url=ontario_payroll_table_url(tax_year),
        )
        tax_document = OfficialHtmlDocument(tax.content)
        section = tax_document.section(
            f"Federal rate for {tax_year}", "Provincial or territorial rates"
        )
        brackets = parse_bracket_section(section, expected_count=5, source_name=tax.source_id)
        limit_row = require_year_row(
            OfficialHtmlDocument(limits.content).table_rows, tax_year, source_name=limits.source_id
        )
        if len(limit_row) < 4:
            raise RuleSourceFormatError(f"Incomplete RRSP limit row for {tax_year}")
        rrsp_limit = Decimal(limit_row[3].replace("$", "").replace(",", "").strip())
        formula_text = OfficialHtmlDocument(formula.content).text
        formula_rates = percentage_values(formula_text)
        if Decimal("0.18") not in formula_rates:
            raise RuleSourceFormatError("Could not verify the RRSP earned-income rate")
        bpa_max, bpa_min = federal_basic_personal_amounts(payroll.content, payroll.source_id)
        employment_amount = canada_employment_amount(payroll.content, payroll.source_id)
        cpp_base_rate, cpp_first_additional_rate = cpp_component_rates(
            payroll.content, payroll.source_id
        )
        sources = (
            rule_source(tax),
            rule_source(limits),
            rule_source(formula),
            rule_source(payroll),
        )
        return (
            PublicRuleSet(
                rule_set_id=f"ca-{tax_year}-official",
                jurisdiction=self.jurisdiction,
                tax_year=tax_year,
                status=RuleStatus.OFFICIAL,
                effective_from=date(tax_year, 1, 1),
                effective_to=date(tax_year, 12, 31),
                sources=sources,
                tax_brackets=(
                    TaxBracketSchedule(
                        code="federal_income_tax",
                        brackets=brackets,
                        source_ids=(tax.source_id,),
                        threshold_indexing=IndexingMetadata(
                            mechanism=IndexingMechanism.CPI,
                            reference_jurisdiction="CA",
                            lag_years=1,
                        ),
                        rate_indexing=IndexingMetadata(mechanism=IndexingMechanism.NONE),
                    ),
                ),
                credits=(
                    RuleParameter(
                        code="federal_basic_personal_amount_max",
                        value=bpa_max,
                        unit=RuleUnit.CAD,
                        source_ids=(payroll.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.CPI),
                    ),
                    RuleParameter(
                        code="federal_basic_personal_amount_min",
                        value=bpa_min,
                        unit=RuleUnit.CAD,
                        source_ids=(payroll.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.CPI),
                    ),
                    RuleParameter(
                        code="canada_employment_amount",
                        value=employment_amount,
                        unit=RuleUnit.CAD,
                        source_ids=(payroll.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.CPI),
                    ),
                ),
                contribution_limits=(
                    RuleParameter(
                        code="rrsp_annual_dollar_limit",
                        value=rrsp_limit,
                        unit=RuleUnit.CAD,
                        source_ids=(limits.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
                    ),
                    RuleParameter(
                        code="rrsp_earned_income_rate",
                        value=Decimal("0.18"),
                        unit=RuleUnit.RATE,
                        source_ids=(formula.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.NONE),
                    ),
                ),
                payroll_parameters=(
                    RuleParameter(
                        code="cpp_employee_rate_base",
                        value=cpp_base_rate,
                        unit=RuleUnit.RATE,
                        source_ids=(payroll.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
                    ),
                    RuleParameter(
                        code="cpp_employee_rate_first_additional",
                        value=cpp_first_additional_rate,
                        unit=RuleUnit.RATE,
                        source_ids=(payroll.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
                    ),
                ),
            ),
        )
