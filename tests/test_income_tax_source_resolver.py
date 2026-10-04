from decimal import Decimal

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.annual_tax_assessment import AnnualTaxAssessment
from domain.annual_tax_value import AnnualTaxValue
from domain.resolved_income_source import ResolvedIncomeSource
from services.income_tax_source_resolver import IncomeTaxSourceResolver, source_fingerprint


def annual_record() -> AnnualEmploymentActual:
    return AnnualEmploymentActual(
        id=1,
        person_id=1,
        tax_year=2025,
        province_of_residence="QC",
        payroll_plan="QPP",
        salary_income=Decimal("90000"),
        bonus=Decimal("0"),
        other_income=Decimal("0"),
        rrsp_contribution=Decimal("0"),
        rrsp_deduction=Decimal("12000"),
        cpp_qpp=Decimal("4000"),
        ei=Decimal("900"),
        qpip=Decimal("400"),
        federal_tax=Decimal("14000"),
        provincial_tax=Decimal("15000"),
        source="Manual annual record",
    )


def assessment() -> AnnualTaxAssessment:
    return AnnualTaxAssessment(
        id=2,
        person_id=1,
        tax_year=2025,
        jurisdiction="CA",
        issued_on="2026-05-01",
        total_income=Decimal("125000"),
        net_income=Decimal("120000"),
        taxable_income=Decimal("118000"),
        net_tax=Decimal("22000"),
        additional_contributions=Decimal("0"),
        tax_withheld=Decimal("22000"),
        balance=Decimal("0"),
        source="CRA notice",
        source_version="2026.10.01",
        document_hash="assessment-hash",
    )


def tax_value(kind: str, amount: str) -> AnnualTaxValue:
    return AnnualTaxValue(
        id=3 if kind == "return" else 4,
        person_id=1,
        tax_year=2025,
        effective_year=2025,
        document_kind=kind,
        jurisdiction="CA",
        concept="employment_income",
        description="Employment income",
        reported_amount=Decimal(amount) if kind == "return" else None,
        determined_amount=Decimal(amount) if kind == "assessment" else None,
        line_code="10100",
        source="Assessment value" if kind == "assessment" else "UFile T1",
        source_version="2026.10.01",
        document_hash=f"{kind}-hash",
    )


def test_resolver_uses_assessment_then_return_then_annual_record() -> None:
    with_all_sources = IncomeTaxSourceResolver(
        [annual_record()],
        [assessment()],
        [tax_value("return", "100000"), tax_value("assessment", "105000")],
    )

    assert with_all_sources.resolve(2025, "total_income").amount == Decimal("125000")
    employment = with_all_sources.resolve(2025, "employment_income")
    assert employment.amount == Decimal("105000")
    assert employment.document_kind == "assessment"

    filed_return = IncomeTaxSourceResolver(
        [annual_record()], [], [tax_value("return", "100000")]
    ).resolve(2025, "employment_income")
    assert filed_return.amount == Decimal("100000")
    assert filed_return.document_kind == "return"

    fallback = IncomeTaxSourceResolver([annual_record()], [], []).resolve(2025, "employment_income")
    assert fallback.amount == Decimal("90000")
    assert fallback.document_kind == "annual_record"


def test_fingerprint_covers_value_provenance_and_source_presence() -> None:
    original = IncomeTaxSourceResolver([], [], [tax_value("return", "100000")]).resolve(
        2025, "employment_income"
    )
    identical = IncomeTaxSourceResolver([], [], [tax_value("return", "100000")]).resolve(
        2025, "employment_income"
    )
    changed_amount = IncomeTaxSourceResolver([], [], [tax_value("return", "100001")]).resolve(
        2025, "employment_income"
    )
    changed_provenance = ResolvedIncomeSource(
        id=original.id,
        concept=original.concept,
        description=original.description,
        document_kind=original.document_kind,
        jurisdiction=original.jurisdiction,
        reported_amount=original.reported_amount,
        determined_amount=original.determined_amount,
        line_code=original.line_code,
        source=original.source,
        source_version=original.source_version,
        document_hash="different-hash",
    )
    absent = ResolvedIncomeSource.absent("employment_income", "Employment income")

    assert source_fingerprint(original) == source_fingerprint(identical)
    assert source_fingerprint(original) != source_fingerprint(changed_amount)
    assert source_fingerprint(original) != source_fingerprint(changed_provenance)
    assert source_fingerprint(original) != source_fingerprint(absent)
