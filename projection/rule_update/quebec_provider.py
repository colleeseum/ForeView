"""Official Quebec income-tax and QPP rule provider."""

from __future__ import annotations

import re
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

from .cra_payroll_csv import payroll_record
from .errors import RuleSourceFormatError
from .html_document import OfficialHtmlDocument
from .parsing import (
    decimal_value,
    parse_bracket_section,
    rate_value,
    year_rows,
)
from .source_metadata import rule_source
from .source_retriever import SourceRetriever


class QuebecRuleProvider:
    provider_id = "ca.qc"
    jurisdiction = "CA-QC"

    TAX_URL = (
        "https://www.revenuquebec.ca/en/citizens/income-tax-return/"
        "completing-your-income-tax-return/income-tax-rates/?wbdisable=true"
    )
    QPP_URL = (
        "https://www.retraitequebec.gouv.qc.ca/en/programs/quebec-pension-plan/"
        "work-contributions/pensionable-earnings-contributions"
    )
    ABATEMENT_URL = (
        "https://www.canada.ca/en/department-finance/programs/federal-transfers/"
        "quebec-abatement.html?wbdisable=true"
    )
    EI_URL_TEMPLATE = (
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pub/t4127-jan/ei-01-{year_short}e.csv"
    )
    QPIP_URL_TEMPLATE = (
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pub/"
        "t4127-jan/qpip-01-{year_short}e.csv"
    )
    USER_AGENT = "RetirementFinanceRuleUpdater/1.0 (+private-use)"

    def fetch(self, tax_year: int, retriever: SourceRetriever) -> tuple[PublicRuleSet, ...]:
        tax = retriever.retrieve(
            source_id=f"rq-income-tax-rates-{tax_year}",
            title=f"Quebec income tax rates for {tax_year}",
            publisher="Revenu Québec",
            url=self.TAX_URL,
            user_agent=self.USER_AGENT,
        )
        qpp = retriever.retrieve(
            source_id="rq-qpp-pensionable-earnings-contributions",
            title="QPP pensionable earnings and contributions",
            publisher="Retraite Québec",
            url=self.QPP_URL,
            user_agent=self.USER_AGENT,
        )
        abatement = retriever.retrieve(
            source_id="finance-canada-quebec-abatement",
            title="Quebec Abatement",
            publisher="Department of Finance Canada",
            url=self.ABATEMENT_URL,
        )
        ei = retriever.retrieve(
            source_id=f"cra-ei-rates-{tax_year}",
            title=f"Employment Insurance rates and amounts for {tax_year}",
            publisher="Canada Revenue Agency",
            url=self.EI_URL_TEMPLATE.format(year_short=str(tax_year)[-2:]),
        )
        qpip = retriever.retrieve(
            source_id=f"cra-qpip-rates-{tax_year}",
            title=f"Quebec Parental Insurance Plan rates and amounts for {tax_year}",
            publisher="Canada Revenue Agency",
            url=self.QPIP_URL_TEMPLATE.format(year_short=str(tax_year)[-2:]),
        )
        tax_document = OfficialHtmlDocument(tax.content)
        section = tax_document.section(
            f"Income tax rates for {tax_year}", f"Income tax rates for {tax_year - 1}"
        )
        brackets = parse_bracket_section(section, expected_count=4, source_name=tax.source_id)
        rows = year_rows(OfficialHtmlDocument(qpp.content).table_rows, tax_year)
        if len(rows) < 2 or len(rows[0]) < 7 or len(rows[1]) < 7:
            raise RuleSourceFormatError(f"Incomplete QPP contribution rows for {tax_year}")
        first, second = rows[0], rows[1]
        ei_values = payroll_record(ei.content, "EI", "QC", ei.source_id)
        qpip_values = payroll_record(qpip.content, "QPIP", "QC", qpip.source_id)
        payroll = (
            self._money("qpp_basic_exemption", first[1], qpp.source_id),
            self._money("qpp_ympe", first[2], qpp.source_id),
            self._money("qpp_yampe", second[2], qpp.source_id),
            self._rate("qpp_employee_rate_first", first[3], qpp.source_id),
            self._rate("qpp_employee_rate_second", second[3], qpp.source_id),
            self._money("qpp_employee_max_first", first[5], qpp.source_id),
            self._money("qpp_employee_max_second", second[5], qpp.source_id),
            self._money_decimal(
                "ei_max_insurable_earnings",
                ei_values["Maximum Annual Insurable Earnings"],
                ei.source_id,
            ),
            self._rate_decimal(
                "ei_employee_rate", ei_values["Employee Contribution Rate"], ei.source_id
            ),
            self._statutory_money(
                "ei_employee_max_premium",
                ei_values["Maximum Annual Employee Premium"],
                ei.source_id,
            ),
            self._money_decimal(
                "qpip_max_insurable_earnings",
                qpip_values["Maximum Annual Insurable Earnings"],
                qpip.source_id,
            ),
            self._rate_decimal(
                "qpip_employee_rate",
                qpip_values["Employee Contribution Rate"],
                qpip.source_id,
            ),
            self._statutory_money(
                "qpip_employee_max_premium",
                qpip_values["Maximum Annual Employee Premium"],
                qpip.source_id,
            ),
        )
        abatement_match = re.search(
            r"reduction of\s+(16\.5)\s+percentage points",
            OfficialHtmlDocument(abatement.content).text,
            flags=re.IGNORECASE,
        )
        if abatement_match is None:
            raise RuleSourceFormatError("Could not verify the Quebec federal tax abatement")
        abatement_rate = Decimal(abatement_match.group(1)) / Decimal("100")
        return (
            PublicRuleSet(
                rule_set_id=f"ca-qc-{tax_year}-official",
                jurisdiction=self.jurisdiction,
                tax_year=tax_year,
                status=RuleStatus.OFFICIAL,
                effective_from=date(tax_year, 1, 1),
                effective_to=date(tax_year, 12, 31),
                sources=(
                    rule_source(tax),
                    rule_source(qpp),
                    rule_source(abatement),
                    rule_source(ei),
                    rule_source(qpip),
                ),
                tax_brackets=(
                    TaxBracketSchedule(
                        code="quebec_income_tax",
                        brackets=brackets,
                        source_ids=(tax.source_id,),
                        threshold_indexing=IndexingMetadata(
                            mechanism=IndexingMechanism.QUEBEC_INDEXATION,
                            reference_jurisdiction="CA-QC",
                            lag_years=1,
                        ),
                        rate_indexing=IndexingMetadata(mechanism=IndexingMechanism.NONE),
                    ),
                ),
                payroll_parameters=payroll,
                other_parameters=(
                    RuleParameter(
                        code="quebec_federal_tax_abatement_rate",
                        value=abatement_rate,
                        unit=RuleUnit.RATE,
                        source_ids=(abatement.source_id,),
                        indexing=IndexingMetadata(mechanism=IndexingMechanism.NONE),
                    ),
                ),
            ),
        )

    @staticmethod
    def _money(code: str, value: str, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=decimal_value(value),
            unit=RuleUnit.CAD,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.WAGE_GROWTH),
        )

    @staticmethod
    def _rate(code: str, value: str, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=rate_value(value),
            unit=RuleUnit.RATE,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
        )

    @staticmethod
    def _money_decimal(code: str, value: Decimal, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=value,
            unit=RuleUnit.CAD,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.WAGE_GROWTH),
        )

    @staticmethod
    def _rate_decimal(code: str, value: Decimal, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=value,
            unit=RuleUnit.RATE,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
        )

    @staticmethod
    def _statutory_money(code: str, value: Decimal, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=value,
            unit=RuleUnit.CAD,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
        )
