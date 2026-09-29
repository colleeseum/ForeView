from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from domain.annual_tax_value import AnnualTaxValue
from domain.money import from_cents, to_cents
from domain.parsed_tax_value import ParsedTaxValue


class AnnualTaxValueRepository:
    """Persist normalized values extracted from annual tax documents."""

    _DOCUMENT_KINDS = {"return", "assessment"}

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace_document(
        self,
        person_id: int,
        tax_year: int,
        document_kind: str,
        jurisdiction: str,
        source: str,
        source_version: str,
        document_hash: str,
        values: Iterable[ParsedTaxValue],
    ) -> list[AnnualTaxValue]:
        kind = document_kind.strip().lower()
        if kind not in self._DOCUMENT_KINDS:
            raise ValueError("Tax document kind must be return or assessment")
        code = jurisdiction.strip().upper()
        if not code:
            raise ValueError("Tax jurisdiction is required")
        parsed_values = tuple(values)
        self._connection.execute(
            """DELETE FROM annual_tax_values
                WHERE person_id = ? AND tax_year = ?
                  AND document_kind = ? AND jurisdiction = ?""",
            (person_id, tax_year, kind, code),
        )
        for value in parsed_values:
            self._insert(
                person_id,
                tax_year,
                kind,
                code,
                source,
                source_version,
                document_hash,
                value,
            )
        return self.list_for_document(person_id, tax_year, kind, code)

    def upsert_value(
        self,
        person_id: int,
        tax_year: int,
        document_kind: str,
        jurisdiction: str,
        source: str,
        source_version: str,
        document_hash: str,
        value: ParsedTaxValue,
    ) -> AnnualTaxValue:
        kind = document_kind.strip().lower()
        code = jurisdiction.strip().upper()
        if kind not in self._DOCUMENT_KINDS:
            raise ValueError("Tax document kind must be return or assessment")
        if not code:
            raise ValueError("Tax jurisdiction is required")
        self._insert(
            person_id,
            tax_year,
            kind,
            code,
            source,
            source_version,
            document_hash,
            value,
        )
        result = self.get(
            person_id,
            tax_year,
            kind,
            code,
            value.concept,
            value.effective_year or tax_year,
        )
        if result is None:  # pragma: no cover
            raise RuntimeError("Tax value could not be retrieved")
        return result

    def _insert(
        self,
        person_id: int,
        tax_year: int,
        document_kind: str,
        jurisdiction: str,
        source: str,
        source_version: str,
        document_hash: str,
        value: ParsedTaxValue,
    ) -> None:
        concept = value.concept.strip()
        if not concept:
            raise ValueError("Tax concept is required")
        if value.reported_amount is None and value.determined_amount is None:
            raise ValueError("A tax value requires a reported or determined amount")
        effective_year = value.effective_year or tax_year
        self._connection.execute(
            """INSERT INTO annual_tax_values(
                   person_id, tax_year, effective_year, document_kind, jurisdiction,
                   concept, description, reported_amount_cents, determined_amount_cents,
                   line_code, source, source_version, document_hash
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(
                   person_id, tax_year, document_kind, jurisdiction, concept, effective_year
               ) DO UPDATE SET
                   description = excluded.description,
                   reported_amount_cents = excluded.reported_amount_cents,
                   determined_amount_cents = excluded.determined_amount_cents,
                   line_code = excluded.line_code,
                   source = excluded.source,
                   source_version = excluded.source_version,
                   document_hash = excluded.document_hash""",
            (
                person_id,
                tax_year,
                effective_year,
                document_kind,
                jurisdiction,
                concept,
                value.description.strip(),
                to_cents(value.reported_amount) if value.reported_amount is not None else None,
                to_cents(value.determined_amount) if value.determined_amount is not None else None,
                value.line_code,
                source,
                source_version,
                document_hash,
            ),
        )

    def get(
        self,
        person_id: int,
        tax_year: int,
        document_kind: str,
        jurisdiction: str,
        concept: str,
        effective_year: int,
    ) -> AnnualTaxValue | None:
        row = self._connection.execute(
            """SELECT id, person_id, tax_year, effective_year, document_kind,
                      jurisdiction, concept, description, reported_amount_cents,
                      determined_amount_cents, line_code, source, source_version, document_hash
                 FROM annual_tax_values
                WHERE person_id = ? AND tax_year = ? AND document_kind = ?
                  AND jurisdiction = ? AND concept = ? AND effective_year = ?""",
            (person_id, tax_year, document_kind, jurisdiction, concept, effective_year),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_for_document(
        self, person_id: int, tax_year: int, document_kind: str, jurisdiction: str
    ) -> list[AnnualTaxValue]:
        rows = self._connection.execute(
            """SELECT id, person_id, tax_year, effective_year, document_kind,
                      jurisdiction, concept, description, reported_amount_cents,
                      determined_amount_cents, line_code, source, source_version, document_hash
                 FROM annual_tax_values
                WHERE person_id = ? AND tax_year = ? AND document_kind = ?
                  AND jurisdiction = ?
                ORDER BY effective_year, CASE WHEN line_code GLOB '[0-9]*' THEN 0 ELSE 1 END,
                         CAST(line_code AS INTEGER), concept""",
            (person_id, tax_year, document_kind, jurisdiction),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_for_person(self, person_id: int) -> list[AnnualTaxValue]:
        rows = self._connection.execute(
            """SELECT id, person_id, tax_year, effective_year, document_kind,
                      jurisdiction, concept, description, reported_amount_cents,
                      determined_amount_cents, line_code, source, source_version, document_hash
                 FROM annual_tax_values WHERE person_id = ?
                ORDER BY tax_year DESC, document_kind, jurisdiction, effective_year, concept""",
            (person_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> AnnualTaxValue:
        return AnnualTaxValue(
            id=AnnualTaxValueRepository._required_int(row[0]),
            person_id=AnnualTaxValueRepository._required_int(row[1]),
            tax_year=AnnualTaxValueRepository._required_int(row[2]),
            effective_year=AnnualTaxValueRepository._required_int(row[3]),
            document_kind=str(row[4]),
            jurisdiction=str(row[5]),
            concept=str(row[6]),
            description=str(row[7]),
            reported_amount=from_cents(row[8]) if row[8] is not None else None,
            determined_amount=from_cents(row[9]) if row[9] is not None else None,
            line_code=str(row[10]) if row[10] is not None else None,
            source=str(row[11]),
            source_version=str(row[12]),
            document_hash=str(row[13]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Tax value identifier must be an integer")
        return value
