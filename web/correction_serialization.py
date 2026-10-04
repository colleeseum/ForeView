from __future__ import annotations

from typing import Any

from domain.factual_correction_revision import FactualCorrectionRevision
from domain.income_tax_concept import income_tax_concept
from domain.resolved_income_source import ResolvedIncomeSource
from services.income_tax_source_resolver import source_fingerprint


def correction_revision_json(
    revision: FactualCorrectionRevision,
    current_source: ResolvedIncomeSource,
) -> dict[str, Any]:
    source_amount = (
        revision.source_determined_amount
        if revision.source_determined_amount is not None
        else revision.source_reported_amount
    )
    return {
        "id": revision.id,
        "person_id": revision.person_id,
        "tax_year": revision.tax_year,
        "concept": revision.concept,
        "label": income_tax_concept(revision.concept).label,
        "revision_number": revision.revision_number,
        "revision_kind": revision.revision_kind,
        "correct_amount": (
            str(revision.correct_amount) if revision.correct_amount is not None else None
        ),
        "reason": revision.reason,
        "created_at": revision.created_at,
        "review_required": (
            revision.is_active and revision.fingerprint != source_fingerprint(current_source)
        ),
        "source_at_correction": {
            "amount": str(source_amount) if source_amount is not None else None,
            "document_kind": revision.source_document_kind,
            "jurisdiction": revision.source_jurisdiction,
            "line_code": revision.source_line_code,
            "source": revision.source_name,
            "source_version": revision.source_version,
            "document_hash": revision.source_document_hash,
        },
        "current_underlying": resolved_source_json(current_source),
    }


def resolved_source_json(source: ResolvedIncomeSource) -> dict[str, Any]:
    return {
        "amount": str(source.amount) if source.amount is not None else None,
        "document_kind": source.document_kind,
        "jurisdiction": source.jurisdiction,
        "line_code": source.line_code,
        "source": source.source,
        "source_version": source.source_version,
        "document_hash": source.document_hash,
    }
