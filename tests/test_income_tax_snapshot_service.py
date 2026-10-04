from decimal import Decimal

from domain.annual_employment_actual import AnnualEmploymentActual
from domain.annual_tax_assessment import AnnualTaxAssessment
from domain.annual_tax_value import AnnualTaxValue
from services.income_tax_snapshot_service import IncomeTaxSnapshotService


def annual_record(
    year: int, salary: str = "100000", *, source: str = "UFile T1"
) -> AnnualEmploymentActual:
    return AnnualEmploymentActual(
        id=year,
        person_id=1,
        tax_year=year,
        province_of_residence="QC",
        payroll_plan="CPP",
        salary_income=Decimal(salary),
        bonus=Decimal("0"),
        other_income=Decimal("0"),
        rrsp_contribution=Decimal("0"),
        rrsp_deduction=Decimal("12000"),
        cpp_qpp=Decimal("4000"),
        ei=Decimal("900"),
        qpip=Decimal("400"),
        federal_tax=Decimal("14000"),
        provincial_tax=Decimal("15000"),
        source=source,
    )


def tax_value(
    year: int,
    concept: str,
    amount: str,
    *,
    kind: str = "return",
    jurisdiction: str = "CA",
    determined: bool = False,
) -> AnnualTaxValue:
    value = Decimal(amount)
    return AnnualTaxValue(
        id=1,
        person_id=1,
        tax_year=year,
        effective_year=year,
        document_kind=kind,
        jurisdiction=jurisdiction,
        concept=concept,
        description=concept,
        reported_amount=None if determined else value,
        determined_amount=value if determined else None,
        line_code="10100",
        source="Assessment" if kind == "assessment" else "UFile T1",
        source_version="2026.09.29",
        document_hash="abc",
    )


def assessment(year: int, total_income: str) -> AnnualTaxAssessment:
    return AnnualTaxAssessment(
        id=1,
        person_id=1,
        tax_year=year,
        jurisdiction="CA",
        issued_on=f"{year + 1}-05-01",
        total_income=Decimal(total_income),
        net_income=Decimal(total_income),
        taxable_income=Decimal(total_income),
        net_tax=Decimal("20000"),
        additional_contributions=Decimal("0"),
        tax_withheld=Decimal("20000"),
        balance=Decimal("0"),
        source="CRA notice",
        source_version="2026.09.29",
        document_hash="def",
    )


def test_snapshot_uses_latest_year_without_borrowing_older_values():
    snapshot = IncomeTaxSnapshotService().build(
        [annual_record(2025, "110000")],
        [assessment(2024, "99000")],
        [tax_value(2024, "interest_investment_income", "500")],
    )

    assert snapshot is not None
    assert snapshot.tax_year == 2025
    assert snapshot.available_years == (2025, 2024)
    values = {value.concept: value for value in snapshot.values}
    assert values["employment_income"].amount == Decimal("110000")
    assert "interest_investment_income" not in values


def test_snapshot_prefers_assessed_values_and_preserves_provenance():
    snapshot = IncomeTaxSnapshotService().build(
        [annual_record(2025)],
        [assessment(2025, "125000")],
        [
            tax_value(
                2025,
                "employment_income",
                "100000",
                kind="assessment",
                jurisdiction="CA-QC",
                determined=True,
            ),
            tax_value(2025, "interest_investment_income", "725.50"),
        ],
    )

    assert snapshot is not None
    values = {value.concept: value for value in snapshot.values}
    # employment_income is not in assessment mapping, so it comes from tax_value
    assert values["employment_income"].amount == Decimal("100000")
    assert values["employment_income"].document_kind == "assessment"
    assert values["employment_income"].source == "Assessment"

    # total_income IS in assessment mapping
    assert values["total_income"].amount == Decimal("125000")
    assert values["total_income"].source == "CRA notice"

    assert values["interest_investment_income"].amount == Decimal("725.50")


def test_snapshot_full_precedence_order():
    """Test that assessment > filed return > manual fallback precedence is maintained."""
    snapshot = IncomeTaxSnapshotService().build(
        [annual_record(2025, "90000", source="Manual")],
        [],
        [
            tax_value(2025, "employment_income", "100000", kind="return"),
            tax_value(
                2025,
                "employment_income",
                "125000",
                kind="assessment",
                jurisdiction="CA-QC",
                determined=True,
            ),
        ],
        year=2025,
    )

    assert snapshot is not None
    values = {value.concept: value for value in snapshot.values}

    assert values["employment_income"].amount == Decimal("125000")
    assert values["employment_income"].source == "Assessment"
    assert values["employment_income"].document_kind == "assessment"


def test_snapshot_manual_fallback_used():
    """Test that manual fallback is used when neither assessment nor filed return exist."""
    snapshot = IncomeTaxSnapshotService().build(
        [annual_record(2025, "90000", source="Manual")],
        [],
        [],
        year=2025,
    )

    assert snapshot is not None
    values = {value.concept: value for value in snapshot.values}

    assert values["employment_income"].amount == Decimal("90000")
    assert values["employment_income"].source == "Manual"
    assert values["employment_income"].document_kind == "annual_record"
