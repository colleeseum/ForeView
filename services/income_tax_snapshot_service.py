from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.annual_tax_assessment import AnnualTaxAssessment
from domain.annual_tax_value import AnnualTaxValue
from domain.consolidated_income_value import ConsolidatedIncomeValue
from domain.income_tax_snapshot import IncomeTaxSnapshot
from repositories.correction_repository import CorrectionRepository


class IncomeTaxSnapshotService:
    """Resolve a compact annual view from returns, assessments, and manual facts."""

    _CONCEPTS = (
        ("employment_income", "Employment income", "salary_income"),
        ("oas_income", "OAS income", None),
        ("cpp_qpp_benefits", "CPP/QPP benefits", None),
        ("other_pension_income", "Other pension income", None),
        ("interest_investment_income", "Interest and investment income", None),
        ("total_income", "Total income", None),
        ("taxable_income", "Taxable income", None),
        ("rrsp_deduction", "RRSP deduction", "rrsp_deduction"),
        ("net_federal_tax", "Net federal tax", "federal_tax"),
        ("provincial_income_tax", "Net provincial tax", "provincial_tax"),
    )

    def __init__(self, correction_repository: CorrectionRepository | None = None) -> None:
        self._correction_repository = correction_repository

    def build(
        self,
        records: Iterable[AnnualEmploymentActual],
        assessments: Iterable[AnnualTaxAssessment],
        tax_values: Iterable[AnnualTaxValue],
        *,
        person_id: int | None = None,
        year: int | None = None,
    ) -> IncomeTaxSnapshot | None:
        """
        Build an IncomeTaxSnapshot for a specific year.

        Precedence:
        1. Correction (explicit factual correction) - takes precedence over all other sources
        2. AnnualTaxAssessment (Assessment)
        3. AnnualTaxValue (T1/Filed Return)
        4. AnnualEmploymentActual (Manual/Factual Record) - only if fallback is defined for the concept.
        """
        annual_records = tuple(records)
        annual_assessments = tuple(assessments)
        values = tuple(tax_values)
        years = tuple(
            sorted(
                {
                    *(record.tax_year for record in annual_records),
                    *(assessment.tax_year for assessment in annual_assessments),
                    *(value.tax_year for value in values),
                },
                reverse=True,
            )
        )
        if not years:
            return None
        selected_year = year if year is not None else years[0]
        if selected_year not in years:
            return None

        record = next((item for item in annual_records if item.tax_year == selected_year), None)
        selected: list[ConsolidatedIncomeValue] = []
        for concept, label, fallback_attribute in self._CONCEPTS:
            # Check for correction first (highest precedence)
            resolved = None
            if self._correction_repository and person_id is not None:
                correction = self._correction_repository.get(person_id, selected_year, concept)
                if correction is not None:
                    if correction.correct_amount is not None:
                        resolved = ConsolidatedIncomeValue(
                            concept=concept,
                            label=label,
                            amount=correction.correct_amount,
                            source="Corrected value",
                            document_kind="correction",
                            jurisdiction=correction.source_jurisdiction,
                        )

            # If no correction or correction failed, resolve through normal precedence
            if resolved is None:
                resolved = self._resolve_assessment(
                    annual_assessments, selected_year, concept, label
                ) or self._resolve_tax_value(values, selected_year, concept, label)

            # 4: Try Manual fallback if both Assessment and T1 failed
            if resolved is None and record is not None and fallback_attribute is not None:
                resolved = ConsolidatedIncomeValue(
                    concept=concept,
                    label=label,
                    amount=self._record_amount(record, fallback_attribute),
                    source=record.source or "Manual annual record",
                    document_kind="annual_record",
                    jurisdiction=record.province_of_residence,
                )
            if resolved is not None:
                selected.append(resolved)
        return IncomeTaxSnapshot(selected_year, years, tuple(selected))

    @staticmethod
    def _resolve_assessment(
        assessments: tuple[AnnualTaxAssessment, ...],
        tax_year: int,
        concept: str,
        label: str,
    ) -> ConsolidatedIncomeValue | None:
        mapping = {
            "total_income": ("total_income", "CA"),
            "taxable_income": ("taxable_income", "CA"),
            "net_federal_tax": ("net_tax", "CA"),
            "provincial_income_tax": ("net_tax", "CA-QC"),
        }
        field = mapping.get(concept)
        if field is None:
            return None
        attribute, jurisdiction = field
        assessment = next(
            (
                item
                for item in assessments
                if item.tax_year == tax_year and item.jurisdiction == jurisdiction
            ),
            None,
        )
        if assessment is None:
            return None
        amount = getattr(assessment, attribute)
        if not isinstance(amount, Decimal):  # pragma: no cover
            raise TypeError("Assessment amount must be a Decimal")
        return ConsolidatedIncomeValue(
            concept=concept,
            label=label,
            amount=amount,
            source=assessment.source,
            document_kind="assessment",
            jurisdiction=assessment.jurisdiction,
        )

    @staticmethod
    def _record_amount(record: AnnualEmploymentActual, attribute: str) -> Decimal:
        amount = getattr(record, attribute)
        if not isinstance(amount, Decimal):  # pragma: no cover
            raise TypeError("Annual record amount must be a Decimal")
        return amount

    @staticmethod
    def _resolve_tax_value(
        values: tuple[AnnualTaxValue, ...], tax_year: int, concept: str, label: str
    ) -> ConsolidatedIncomeValue | None:
        source_concept = "quebec_income_tax" if concept == "provincial_income_tax" else concept
        candidates = tuple(
            value
            for value in values
            if value.tax_year == tax_year
            and value.effective_year == tax_year
            and value.concept == source_concept
            and (value.determined_amount is not None or value.reported_amount is not None)
        )
        if not candidates:
            return None
        chosen = max(candidates, key=IncomeTaxSnapshotService._priority)
        amount = (
            chosen.determined_amount
            if chosen.determined_amount is not None
            else chosen.reported_amount
        )
        if amount is None:  # pragma: no cover
            return None
        return ConsolidatedIncomeValue(
            concept=concept,
            label=label,
            amount=amount,
            source=chosen.source,
            document_kind=chosen.document_kind,
            jurisdiction=chosen.jurisdiction,
            line_code=chosen.line_code,
        )

    @staticmethod
    def _priority(value: AnnualTaxValue) -> tuple[int, int, int]:
        return (
            1 if value.document_kind == "assessment" else 0,
            1 if value.determined_amount is not None else 0,
            1 if value.jurisdiction == "CA" else 0,
        )
