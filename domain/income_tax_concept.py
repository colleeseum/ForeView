from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class IncomeTaxConcept:
    """A factual concept supported by the consolidated income and tax view."""

    key: str
    label: str
    annual_record_attribute: str | None = None


INCOME_TAX_CONCEPTS: Final = (
    IncomeTaxConcept("employment_income", "Employment income", "salary_income"),
    IncomeTaxConcept("oas_income", "OAS income"),
    IncomeTaxConcept("cpp_qpp_benefits", "CPP/QPP benefits"),
    IncomeTaxConcept("other_pension_income", "Other pension income"),
    IncomeTaxConcept(
        "interest_investment_income",
        "Interest and investment income",
    ),
    IncomeTaxConcept("total_income", "Total income"),
    IncomeTaxConcept("taxable_income", "Taxable income"),
    IncomeTaxConcept("rrsp_deduction", "RRSP deduction", "rrsp_deduction"),
    IncomeTaxConcept("net_federal_tax", "Net federal tax", "federal_tax"),
    IncomeTaxConcept(
        "provincial_income_tax",
        "Net provincial tax",
        "provincial_tax",
    ),
)

INCOME_TAX_CONCEPTS_BY_KEY: Final = MappingProxyType(
    {concept.key: concept for concept in INCOME_TAX_CONCEPTS}
)


def income_tax_concept(key: str) -> IncomeTaxConcept:
    try:
        return INCOME_TAX_CONCEPTS_BY_KEY[key]
    except KeyError as error:
        raise ValueError(f"Unsupported income and tax concept: {key}") from error
