from __future__ import annotations

import sqlite3

from domain.annual_tax_assessment import AnnualTaxAssessment
from domain.money import MoneyInput, from_cents, to_cents


class AnnualTaxAssessmentRepository:
    """Persist assessed tax results separately from filed return values."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert(
        self,
        person_id: int,
        tax_year: int,
        jurisdiction: str,
        issued_on: str,
        *,
        total_income: MoneyInput,
        net_income: MoneyInput,
        taxable_income: MoneyInput,
        net_tax: MoneyInput,
        additional_contributions: MoneyInput = 0,
        tax_withheld: MoneyInput = 0,
        balance: MoneyInput = 0,
        source: str,
        source_version: str,
        document_hash: str,
    ) -> AnnualTaxAssessment:
        code = jurisdiction.strip().upper()
        if code not in {"CA", "CA-QC"}:
            raise ValueError("Unsupported assessment jurisdiction")
        amounts = tuple(
            to_cents(value)
            for value in (
                total_income,
                net_income,
                taxable_income,
                net_tax,
                additional_contributions,
                tax_withheld,
                balance,
            )
        )
        if any(value < 0 for value in amounts[:6]):
            raise ValueError("Assessment totals other than the balance cannot be negative")
        self._connection.execute(
            """INSERT INTO annual_tax_assessments(
                   person_id, tax_year, jurisdiction, issued_on, total_income_cents,
                   net_income_cents, taxable_income_cents, net_tax_cents,
                   additional_contributions_cents, tax_withheld_cents, balance_cents,
                   source, source_version, document_hash
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(person_id, tax_year, jurisdiction) DO UPDATE SET
                   issued_on = excluded.issued_on,
                   total_income_cents = excluded.total_income_cents,
                   net_income_cents = excluded.net_income_cents,
                   taxable_income_cents = excluded.taxable_income_cents,
                   net_tax_cents = excluded.net_tax_cents,
                   additional_contributions_cents = excluded.additional_contributions_cents,
                   tax_withheld_cents = excluded.tax_withheld_cents,
                   balance_cents = excluded.balance_cents,
                   source = excluded.source,
                   source_version = excluded.source_version,
                   document_hash = excluded.document_hash""",
            (person_id, tax_year, code, issued_on, *amounts, source, source_version, document_hash),
        )
        result = self.get(person_id, tax_year, code)
        if result is None:  # pragma: no cover
            raise RuntimeError("Tax assessment could not be retrieved")
        return result

    def get(self, person_id: int, tax_year: int, jurisdiction: str) -> AnnualTaxAssessment | None:
        row = self._connection.execute(
            """SELECT id, person_id, tax_year, jurisdiction, issued_on,
                      total_income_cents, net_income_cents, taxable_income_cents,
                      net_tax_cents, additional_contributions_cents, tax_withheld_cents,
                      balance_cents, source, source_version, document_hash
                 FROM annual_tax_assessments
                WHERE person_id = ? AND tax_year = ? AND jurisdiction = ?""",
            (person_id, tax_year, jurisdiction),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_person(self, person_id: int) -> list[AnnualTaxAssessment]:
        rows = self._connection.execute(
            """SELECT id, person_id, tax_year, jurisdiction, issued_on,
                      total_income_cents, net_income_cents, taxable_income_cents,
                      net_tax_cents, additional_contributions_cents, tax_withheld_cents,
                      balance_cents, source, source_version, document_hash
                 FROM annual_tax_assessments
                WHERE person_id = ? ORDER BY tax_year DESC, jurisdiction""",
            (person_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> AnnualTaxAssessment:
        return AnnualTaxAssessment(
            id=AnnualTaxAssessmentRepository._required_int(row[0]),
            person_id=AnnualTaxAssessmentRepository._required_int(row[1]),
            tax_year=AnnualTaxAssessmentRepository._required_int(row[2]),
            jurisdiction=str(row[3]),
            issued_on=str(row[4]),
            total_income=from_cents(row[5]),
            net_income=from_cents(row[6]),
            taxable_income=from_cents(row[7]),
            net_tax=from_cents(row[8]),
            additional_contributions=from_cents(row[9]),
            tax_withheld=from_cents(row[10]),
            balance=from_cents(row[11]),
            source=str(row[12]),
            source_version=str(row[13]),
            document_hash=str(row[14]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Tax assessment identifier must be an integer")
        return value
