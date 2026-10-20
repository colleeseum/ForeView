# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from decimal import Decimal

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.annual_tax_assessment import AnnualTaxAssessment
from domain.annual_tax_value import AnnualTaxValue
from domain.income_tax_concept import income_tax_concept
from domain.money import to_cents
from domain.resolved_income_source import ResolvedIncomeSource

_ASSESSMENT_FIELDS = {
    "total_income": ("total_income", "CA"),
    "taxable_income": ("taxable_income", "CA"),
    "net_federal_tax": ("net_tax", "CA"),
    "provincial_income_tax": ("net_tax", "CA-QC"),
}


class IncomeTaxSourceResolver:
    """Resolve annual factual sources using consolidated snapshot precedence."""

    def __init__(
        self,
        records: Iterable[AnnualEmploymentActual],
        assessments: Iterable[AnnualTaxAssessment],
        tax_values: Iterable[AnnualTaxValue],
    ) -> None:
        self.records = tuple(records)
        self.assessments = tuple(assessments)
        self.tax_values = tuple(tax_values)

    @property
    def available_years(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                {
                    *(record.tax_year for record in self.records),
                    *(assessment.tax_year for assessment in self.assessments),
                    *(value.tax_year for value in self.tax_values),
                },
                reverse=True,
            )
        )

    def resolve(self, tax_year: int, concept: str) -> ResolvedIncomeSource:
        definition = income_tax_concept(concept)
        return (
            self._assessment(tax_year, concept, definition.label)
            or self._tax_value(tax_year, concept, definition.label)
            or self._annual_record(
                tax_year,
                concept,
                definition.label,
                definition.annual_record_attribute,
            )
            or ResolvedIncomeSource.absent(concept, definition.label)
        )

    def _assessment(self, tax_year: int, concept: str, label: str) -> ResolvedIncomeSource | None:
        mapping = _ASSESSMENT_FIELDS.get(concept)
        if mapping is None:
            return None
        attribute, jurisdiction = mapping
        assessment = next(
            (
                item
                for item in self.assessments
                if item.tax_year == tax_year and item.jurisdiction == jurisdiction
            ),
            None,
        )
        if assessment is None:
            return None
        amount = getattr(assessment, attribute)
        if not isinstance(amount, Decimal):  # pragma: no cover
            raise TypeError("Assessment amount must be a Decimal")
        return ResolvedIncomeSource(
            id=assessment.id,
            concept=concept,
            description=label,
            document_kind="assessment",
            jurisdiction=assessment.jurisdiction,
            reported_amount=None,
            determined_amount=amount,
            line_code=None,
            source=assessment.source,
            source_version=assessment.source_version or None,
            document_hash=assessment.document_hash or None,
        )

    def _tax_value(self, tax_year: int, concept: str, label: str) -> ResolvedIncomeSource | None:
        source_concept = "quebec_income_tax" if concept == "provincial_income_tax" else concept
        candidates = tuple(
            value
            for value in self.tax_values
            if value.tax_year == tax_year
            and value.effective_year == tax_year
            and value.concept == source_concept
            and (value.determined_amount is not None or value.reported_amount is not None)
        )
        if not candidates:
            return None
        chosen = max(candidates, key=self._tax_value_priority)
        return ResolvedIncomeSource(
            id=chosen.id,
            concept=concept,
            description=label,
            document_kind=chosen.document_kind,
            jurisdiction=chosen.jurisdiction,
            reported_amount=chosen.reported_amount,
            determined_amount=chosen.determined_amount,
            line_code=chosen.line_code,
            source=chosen.source,
            source_version=chosen.source_version or None,
            document_hash=chosen.document_hash or None,
        )

    def _annual_record(
        self,
        tax_year: int,
        concept: str,
        label: str,
        fallback_attribute: str | None,
    ) -> ResolvedIncomeSource | None:
        if fallback_attribute is None:
            return None
        record = next((item for item in self.records if item.tax_year == tax_year), None)
        if record is None:
            return None
        amount = getattr(record, fallback_attribute)
        if not isinstance(amount, Decimal):  # pragma: no cover
            raise TypeError("Annual record amount must be a Decimal")
        return ResolvedIncomeSource(
            id=record.id,
            concept=concept,
            description=label,
            document_kind="annual_record",
            jurisdiction=record.province_of_residence,
            reported_amount=amount,
            determined_amount=None,
            line_code=None,
            source=record.source or "Manual annual record",
            source_version=None,
            document_hash=None,
        )

    @staticmethod
    def _tax_value_priority(value: AnnualTaxValue) -> tuple[int, int, int]:
        return (
            1 if value.document_kind == "assessment" else 0,
            1 if value.determined_amount is not None else 0,
            1 if value.jurisdiction == "CA" else 0,
        )


def source_fingerprint(source: ResolvedIncomeSource) -> str:
    """Hash the complete resolved value and its available provenance."""
    amount = source.amount
    payload = {
        "amount_cents": to_cents(amount) if amount is not None else None,
        "document_hash": source.document_hash,
        "document_kind": source.document_kind,
        "has_value": source.has_value,
        "jurisdiction": source.jurisdiction,
        "line_code": source.line_code,
        "source": source.source,
        "source_version": source.source_version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
