"""CRA income-tax and CPP rules for provinces and territories outside Quebec."""

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

from .cra_payroll_csv import payroll_record
from .cra_payroll_tables import (
    MANITOBA_PHASEOUT_URL,
    manitoba_payroll_table_url,
    manitoba_tax_parameters,
    ontario_payroll_table_url,
    ontario_tax_parameters,
)
from .errors import RuleSourceFormatError
from .federal_provider import FederalRuleProvider
from .html_document import OfficialHtmlDocument
from .parsing import labeled_amount, labeled_rates, money_values, parse_variable_bracket_section
from .source_metadata import rule_source
from .source_retriever import SourceRetriever

_JURISDICTIONS = (
    ("ca.ab", "CA-AB", "Alberta", "British Columbia"),
    ("ca.bc", "CA-BC", "British Columbia", "Manitoba"),
    ("ca.mb", "CA-MB", "Manitoba", "New Brunswick"),
    ("ca.nb", "CA-NB", "New Brunswick", "Newfoundland and Labrador"),
    ("ca.nl", "CA-NL", "Newfoundland and Labrador", "Northwest Territories"),
    ("ca.nt", "CA-NT", "Northwest Territories", "Nova Scotia"),
    ("ca.ns", "CA-NS", "Nova Scotia", "Nunavut"),
    ("ca.nu", "CA-NU", "Nunavut", "Ontario"),
    ("ca.on", "CA-ON", "Ontario", "Prince Edward Island"),
    ("ca.pe", "CA-PE", "Prince Edward Island", "Quebec"),
    ("ca.sk", "CA-SK", "Saskatchewan", "Yukon"),
    ("ca.yt", "CA-YT", "Yukon", "How tax rates and brackets work"),
)


class CraJurisdictionRuleProvider:
    CPP_URL_TEMPLATE = (
        "https://www.canada.ca/en/employment-social-development/programs/pensions/"
        "pension/statistics/{year}-quarterly-july-september.html?wbdisable=true"
    )
    EI_URL_TEMPLATE = (
        "https://www.canada.ca/content/dam/cra-arc/formspubs/pub/t4127-jan/ei-01-{year_short}e.csv"
    )

    def __init__(
        self,
        provider_id: str,
        jurisdiction: str,
        jurisdiction_name: str,
        next_section_name: str,
    ) -> None:
        self.provider_id = provider_id
        self.jurisdiction = jurisdiction
        self._jurisdiction_name = jurisdiction_name
        self._next_section_name = next_section_name

    def fetch(self, tax_year: int, retriever: SourceRetriever) -> tuple[PublicRuleSet, ...]:
        source_slug = self.provider_id.removeprefix("ca.")
        tax = retriever.retrieve(
            source_id=f"cra-{source_slug}-brackets-{tax_year}",
            title=f"{self._jurisdiction_name} income tax rates and brackets for {tax_year}",
            publisher="Canada Revenue Agency",
            url=FederalRuleProvider.tax_url(tax_year),
        )
        cpp = retriever.retrieve(
            source_id=f"esdc-cpp-figures-{tax_year}",
            title=f"Canada Pension Plan figures for {tax_year}",
            publisher="Employment and Social Development Canada",
            url=self.CPP_URL_TEMPLATE.format(year=tax_year),
        )
        tax_parameter_sources = []
        tax_parameters: tuple[RuleParameter, ...] = ()
        additional_payroll: tuple[RuleParameter, ...] = ()
        if self.jurisdiction == "CA-ON":
            tax_parameters_source = retriever.retrieve(
                source_id=f"cra-payroll-tables-on-{tax_year}",
                title=f"Federal and Ontario payroll deductions tables for {tax_year}",
                publisher="Canada Revenue Agency",
                url=ontario_payroll_table_url(tax_year),
            )
            tax_parameter_sources.append(tax_parameters_source)
            ei_source = retriever.retrieve(
                source_id=f"cra-ei-rates-{tax_year}",
                title=f"Employment Insurance rates and amounts for {tax_year}",
                publisher="Canada Revenue Agency",
                url=self.EI_URL_TEMPLATE.format(year_short=str(tax_year)[-2:]),
            )
            tax_parameter_sources.append(ei_source)
            ei_values = payroll_record(
                ei_source.content, "EI", "Canada except QC", ei_source.source_id
            )
            additional_payroll = (
                self._money(
                    "ei_max_insurable_earnings",
                    ei_values["Maximum Annual Insurable Earnings"],
                    ei_source.source_id,
                ),
                self._rate(
                    "ei_employee_rate",
                    ei_values["Employee Contribution Rate"],
                    ei_source.source_id,
                ),
                self._statutory_money(
                    "ei_employee_max_premium",
                    ei_values["Maximum Annual Employee Premium"],
                    ei_source.source_id,
                ),
            )
            basic, first_threshold, first_rate, second_threshold, second_rate = (
                ontario_tax_parameters(
                    tax_parameters_source.content, tax_parameters_source.source_id
                )
            )
            source_id = tax_parameters_source.source_id
            tax_parameters = (
                self._money("ontario_basic_personal_amount", basic, source_id),
                self._money("ontario_surtax_threshold_first", first_threshold, source_id),
                self._rate("ontario_surtax_rate_first", first_rate, source_id),
                self._money("ontario_surtax_threshold_second", second_threshold, source_id),
                self._rate("ontario_surtax_rate_second", second_rate, source_id),
            )
        elif self.jurisdiction == "CA-MB":
            annual_source = retriever.retrieve(
                source_id=f"cra-payroll-tables-mb-{tax_year}",
                title=f"Federal and Manitoba payroll deductions tables for {tax_year}",
                publisher="Canada Revenue Agency",
                url=manitoba_payroll_table_url(tax_year),
            )
            phaseout_source = retriever.retrieve(
                source_id="cra-manitoba-bpa-phaseout",
                title="Manitoba basic personal amount phaseout",
                publisher="Canada Revenue Agency",
                url=MANITOBA_PHASEOUT_URL,
            )
            tax_parameter_sources.extend((annual_source, phaseout_source))
            basic, phaseout_start, phaseout_end = manitoba_tax_parameters(
                annual_source.content,
                phaseout_source.content,
                annual_source.source_id,
            )
            tax_parameters = (
                self._static_money(
                    "manitoba_basic_personal_amount", basic, annual_source.source_id
                ),
                self._static_money(
                    "manitoba_bpa_phaseout_start", phaseout_start, phaseout_source.source_id
                ),
                self._static_money(
                    "manitoba_bpa_phaseout_end", phaseout_end, phaseout_source.source_id
                ),
            )
        end = (
            self._next_section_name
            if self._next_section_name == "How tax rates and brackets work"
            else f"{self._next_section_name} rate: {tax_year}"
        )
        section = OfficialHtmlDocument(tax.content).section(
            f"{self._jurisdiction_name} rate: {tax_year}", end
        )
        brackets = parse_variable_bracket_section(section, source_name=tax.source_id)
        cpp_rows = OfficialHtmlDocument(cpp.content).table_rows
        first_rates = labeled_rates(
            cpp_rows,
            "Contribution rate for employee/employer",
            source_name=cpp.source_id,
        )
        first_maximums = self._labeled_amounts(
            cpp_rows, "Employee/employer maximum contribution", cpp.source_id
        )
        payroll = (
            self._money(
                "cpp_basic_exemption",
                labeled_amount(cpp_rows, "Year's Basic Exemption", source_name=cpp.source_id),
                cpp.source_id,
            ),
            self._money(
                "cpp_ympe",
                labeled_amount(
                    cpp_rows,
                    "Year's Maximum Pensionable Earnings",
                    source_name=cpp.source_id,
                ),
                cpp.source_id,
            ),
            self._money(
                "cpp_yampe",
                labeled_amount(
                    cpp_rows,
                    "Year's Additional Maximum Pensionable Earnings",
                    source_name=cpp.source_id,
                ),
                cpp.source_id,
            ),
            self._rate("cpp_employee_rate_first", first_rates[0], cpp.source_id),
            self._rate("cpp_employee_rate_second", first_rates[1], cpp.source_id),
            self._money("cpp_employee_max_first", first_maximums[0], cpp.source_id),
            self._money("cpp_employee_max_second", first_maximums[1], cpp.source_id),
        )
        schedule_code = f"{self._jurisdiction_name.lower().replace(' ', '_')}_income_tax"
        return (
            PublicRuleSet(
                rule_set_id=f"{self.jurisdiction.lower()}-{tax_year}-official",
                jurisdiction=self.jurisdiction,
                tax_year=tax_year,
                status=RuleStatus.OFFICIAL,
                effective_from=date(tax_year, 1, 1),
                effective_to=date(tax_year, 12, 31),
                sources=(
                    rule_source(tax),
                    rule_source(cpp),
                    *(rule_source(source) for source in tax_parameter_sources),
                ),
                tax_brackets=(
                    TaxBracketSchedule(
                        code=schedule_code,
                        brackets=brackets,
                        source_ids=(tax.source_id,),
                        threshold_indexing=IndexingMetadata(
                            mechanism=IndexingMechanism.STATUTORY_SCHEDULE,
                            reference_jurisdiction=self.jurisdiction,
                            lag_years=1,
                        ),
                        rate_indexing=IndexingMetadata(mechanism=IndexingMechanism.NONE),
                    ),
                ),
                payroll_parameters=(*payroll, *additional_payroll),
                other_parameters=tax_parameters,
            ),
        )

    @staticmethod
    def _labeled_amounts(
        rows: tuple[tuple[str, ...], ...], label: str, source_id: str
    ) -> list[Decimal]:
        for row in rows:
            if row and label.casefold() in row[0].casefold():
                values = money_values(" ".join(row[1:]))
                if len(values) >= 2:
                    return values
        raise RuleSourceFormatError(f"Could not find both maximum contributions in {source_id}")

    @staticmethod
    def _money(code: str, value: Decimal, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=value,
            unit=RuleUnit.CAD,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.WAGE_GROWTH),
        )

    @staticmethod
    def _rate(code: str, value: Decimal, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=value,
            unit=RuleUnit.RATE,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
        )

    @staticmethod
    def _static_money(code: str, value: Decimal, source_id: str) -> RuleParameter:
        return RuleParameter(
            code=code,
            value=value,
            unit=RuleUnit.CAD,
            source_ids=(source_id,),
            indexing=IndexingMetadata(mechanism=IndexingMechanism.NONE),
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


def cra_jurisdiction_providers() -> tuple[CraJurisdictionRuleProvider, ...]:
    return tuple(CraJurisdictionRuleProvider(*definition) for definition in _JURISDICTIONS)
