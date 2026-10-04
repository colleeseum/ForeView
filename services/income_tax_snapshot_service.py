# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from collections.abc import Iterable

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.annual_tax_assessment import AnnualTaxAssessment
from domain.annual_tax_value import AnnualTaxValue
from domain.consolidated_income_value import ConsolidatedIncomeValue
from domain.income_tax_concept import INCOME_TAX_CONCEPTS
from domain.income_tax_snapshot import IncomeTaxSnapshot
from repositories.correction_repository import CorrectionRepository
from services.income_tax_source_resolver import IncomeTaxSourceResolver


class IncomeTaxSnapshotService:
    """Resolve a compact annual view from returns, assessments, and manual facts."""

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
        resolver = IncomeTaxSourceResolver(records, assessments, tax_values)
        years = resolver.available_years
        if not years:
            return None
        selected_year = year if year is not None else years[0]
        if selected_year not in years:
            return None

        selected: list[ConsolidatedIncomeValue] = []
        for definition in INCOME_TAX_CONCEPTS:
            concept = definition.key
            resolved = None
            if self._correction_repository and person_id is not None:
                correction = self._correction_repository.get(person_id, selected_year, concept)
                if correction is not None and correction.correct_amount is not None:
                    resolved = ConsolidatedIncomeValue(
                        concept=concept,
                        label=definition.label,
                        amount=correction.correct_amount,
                        source="Corrected value",
                        document_kind="correction",
                        jurisdiction=correction.source_jurisdiction,
                    )
            if resolved is None:
                source = resolver.resolve(selected_year, concept)
                if source.amount is not None and source.document_kind is not None:
                    resolved = ConsolidatedIncomeValue(
                        concept=concept,
                        label=definition.label,
                        amount=source.amount,
                        source=source.source,
                        document_kind=source.document_kind,
                        jurisdiction=source.jurisdiction,
                        line_code=source.line_code,
                    )
            if resolved is not None:
                selected.append(resolved)
        return IncomeTaxSnapshot(selected_year, years, tuple(selected))
