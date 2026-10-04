# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
from decimal import Decimal

from domain.factual_correction_revision import FactualCorrectionRevision
from domain.money import from_cents, to_cents
from domain.resolved_income_source import ResolvedIncomeSource


class CorrectionConflictError(RuntimeError):
    """The correction stream changed after the caller read it."""


class CorrectionNotFoundError(LookupError):
    """The requested correction stream does not exist or is inactive."""


class CorrectionRepository:
    """Persist immutable factual-correction revisions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        person_id: int,
        tax_year: int,
        concept: str,
        correct_amount: Decimal,
        reason: str,
        source_at_correction: ResolvedIncomeSource,
        fingerprint: str,
        *,
        expected_revision: int = 0,
    ) -> FactualCorrectionRevision:
        """Create a stream or reactivate its removed latest revision."""
        latest = self.get_latest(person_id, tax_year, concept)
        if latest is None:
            if expected_revision != 0:
                raise CorrectionConflictError("Correction stream revision is stale")
            revision_number = 1
        elif not latest.is_active and expected_revision == latest.revision_number:
            revision_number = latest.revision_number + 1
        else:
            raise CorrectionConflictError("Correction stream already exists")
        try:
            revision_id = self._insert(
                person_id,
                tax_year,
                concept,
                revision_number,
                "create",
                correct_amount,
                reason,
                source_at_correction,
                fingerprint,
            )
        except sqlite3.IntegrityError as error:
            raise CorrectionConflictError("Correction stream already exists") from error
        return self._required_by_id(revision_id)

    def get(self, person_id: int, tax_year: int, concept: str) -> FactualCorrectionRevision | None:
        """Return the active latest revision, or none after removal."""
        latest = self.get_latest(person_id, tax_year, concept)
        return latest if latest is not None and latest.is_active else None

    def get_latest(
        self, person_id: int, tax_year: int, concept: str
    ) -> FactualCorrectionRevision | None:
        row = self._connection.execute(
            """SELECT * FROM corrections
                 WHERE person_id = ? AND tax_year = ? AND concept = ?
                 ORDER BY revision_number DESC
                 LIMIT 1""",
            (person_id, tax_year, concept),
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def get_by_id(self, revision_id: int) -> FactualCorrectionRevision | None:
        row = self._connection.execute(
            "SELECT * FROM corrections WHERE id = ?", (revision_id,)
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def get_history(
        self, person_id: int, tax_year: int, concept: str
    ) -> list[FactualCorrectionRevision]:
        rows = self._connection.execute(
            """SELECT * FROM corrections
                 WHERE person_id = ? AND tax_year = ? AND concept = ?
                 ORDER BY revision_number""",
            (person_id, tax_year, concept),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_for_person(self, person_id: int) -> list[FactualCorrectionRevision]:
        rows = self._connection.execute(
            """SELECT c.*
                 FROM corrections c
                WHERE c.person_id = ?
                  AND c.revision_number = (
                      SELECT MAX(newer.revision_number)
                        FROM corrections newer
                       WHERE newer.person_id = c.person_id
                         AND newer.tax_year = c.tax_year
                         AND newer.concept = c.concept
                  )
                  AND c.revision_kind != 'remove'
                ORDER BY c.tax_year DESC, c.concept""",
            (person_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_for_year(self, person_id: int, tax_year: int) -> list[FactualCorrectionRevision]:
        rows = self._connection.execute(
            """SELECT c.*
                 FROM corrections c
                WHERE c.person_id = ? AND c.tax_year = ?
                  AND c.revision_number = (
                      SELECT MAX(newer.revision_number)
                        FROM corrections newer
                       WHERE newer.person_id = c.person_id
                         AND newer.tax_year = c.tax_year
                         AND newer.concept = c.concept
                  )
                  AND c.revision_kind != 'remove'
                ORDER BY c.concept""",
            (person_id, tax_year),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def edit(
        self,
        person_id: int,
        tax_year: int,
        concept: str,
        correct_amount: Decimal,
        reason: str,
        *,
        expected_revision: int,
    ) -> FactualCorrectionRevision:
        latest = self._active_with_expected_revision(
            person_id, tax_year, concept, expected_revision
        )
        return self._append_copy(latest, "edit", correct_amount=correct_amount, reason=reason)

    def confirm(
        self,
        person_id: int,
        tax_year: int,
        concept: str,
        source_at_confirmation: ResolvedIncomeSource,
        fingerprint: str,
        *,
        expected_revision: int,
    ) -> FactualCorrectionRevision:
        latest = self._active_with_expected_revision(
            person_id, tax_year, concept, expected_revision
        )
        return self._append_confirmation(latest, source_at_confirmation, fingerprint)

    def remove(
        self,
        person_id: int,
        tax_year: int,
        concept: str,
        *,
        expected_revision: int,
    ) -> FactualCorrectionRevision:
        latest = self.get_latest(person_id, tax_year, concept)
        if latest is None:
            raise CorrectionNotFoundError("Correction stream does not exist")
        if not latest.is_active:
            return latest
        if latest.revision_number != expected_revision:
            raise CorrectionConflictError("Correction revision is stale")
        return self._append_copy(latest, "remove")

    def _active_with_expected_revision(
        self, person_id: int, tax_year: int, concept: str, expected_revision: int
    ) -> FactualCorrectionRevision:
        latest = self.get_latest(person_id, tax_year, concept)
        if latest is None or not latest.is_active:
            raise CorrectionNotFoundError("Active correction does not exist")
        if latest.revision_number != expected_revision:
            raise CorrectionConflictError("Correction revision is stale")
        return latest

    def _append_copy(
        self,
        latest: FactualCorrectionRevision,
        revision_kind: str,
        *,
        correct_amount: Decimal | None = None,
        reason: str | None = None,
    ) -> FactualCorrectionRevision:
        amount = latest.correct_amount if correct_amount is None else correct_amount
        current_reason = latest.reason if reason is None else reason
        try:
            row = self._connection.execute(
                """INSERT INTO corrections(
                       person_id, tax_year, concept, revision_number, revision_kind,
                       correct_amount_cents, reason, source_at_correction_id,
                       source_at_correction_document_kind,
                       source_at_correction_jurisdiction,
                       source_at_correction_concept,
                       source_at_correction_description,
                       source_at_correction_reported_amount_cents,
                       source_at_correction_determined_amount_cents,
                       source_at_correction_line_code, source_at_correction_source,
                       source_at_correction_source_version,
                       source_at_correction_document_hash, fingerprint
                   )
                   SELECT person_id, tax_year, concept, revision_number + 1, ?,
                          ?, ?, source_at_correction_id,
                          source_at_correction_document_kind,
                          source_at_correction_jurisdiction,
                          source_at_correction_concept,
                          source_at_correction_description,
                          source_at_correction_reported_amount_cents,
                          source_at_correction_determined_amount_cents,
                          source_at_correction_line_code, source_at_correction_source,
                          source_at_correction_source_version,
                          source_at_correction_document_hash, fingerprint
                     FROM corrections
                    WHERE id = ?
                      AND revision_number = ?
                      AND revision_number = (
                          SELECT MAX(revision_number)
                            FROM corrections
                           WHERE person_id = ? AND tax_year = ? AND concept = ?
                      )
                   RETURNING id""",
                (
                    revision_kind,
                    to_cents(amount) if amount is not None else None,
                    current_reason,
                    latest.id,
                    latest.revision_number,
                    latest.person_id,
                    latest.tax_year,
                    latest.concept,
                ),
            ).fetchone()
        except sqlite3.IntegrityError as error:
            raise CorrectionConflictError("Correction revision is stale") from error
        if row is None:
            raise CorrectionConflictError("Correction revision is stale")
        return self._required_by_id(int(row[0]))

    def _append_confirmation(
        self,
        latest: FactualCorrectionRevision,
        source: ResolvedIncomeSource,
        fingerprint: str,
    ) -> FactualCorrectionRevision:
        try:
            row = self._connection.execute(
                """INSERT INTO corrections(
                       person_id, tax_year, concept, revision_number, revision_kind,
                       correct_amount_cents, reason, source_at_correction_id,
                       source_at_correction_document_kind,
                       source_at_correction_jurisdiction,
                       source_at_correction_concept,
                       source_at_correction_description,
                       source_at_correction_reported_amount_cents,
                       source_at_correction_determined_amount_cents,
                       source_at_correction_line_code, source_at_correction_source,
                       source_at_correction_source_version,
                       source_at_correction_document_hash, fingerprint
                   )
                   SELECT person_id, tax_year, concept, revision_number + 1, 'confirm',
                          correct_amount_cents, reason, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                     FROM corrections
                    WHERE id = ?
                      AND revision_number = ?
                      AND revision_number = (
                          SELECT MAX(revision_number)
                            FROM corrections
                           WHERE person_id = ? AND tax_year = ? AND concept = ?
                      )
                   RETURNING id""",
                (
                    source.id,
                    source.document_kind,
                    source.jurisdiction,
                    source.concept,
                    source.description,
                    to_cents(source.reported_amount)
                    if source.reported_amount is not None
                    else None,
                    to_cents(source.determined_amount)
                    if source.determined_amount is not None
                    else None,
                    source.line_code,
                    source.source,
                    source.source_version,
                    source.document_hash,
                    fingerprint,
                    latest.id,
                    latest.revision_number,
                    latest.person_id,
                    latest.tax_year,
                    latest.concept,
                ),
            ).fetchone()
        except sqlite3.IntegrityError as error:
            raise CorrectionConflictError("Correction revision is stale") from error
        if row is None:
            raise CorrectionConflictError("Correction revision is stale")
        return self._required_by_id(int(row[0]))

    def _insert(
        self,
        person_id: int,
        tax_year: int,
        concept: str,
        revision_number: int,
        revision_kind: str,
        correct_amount: Decimal,
        reason: str,
        source: ResolvedIncomeSource,
        fingerprint: str,
    ) -> int:
        cursor = self._connection.execute(
            """INSERT INTO corrections(
                   person_id, tax_year, concept, revision_number, revision_kind,
                   correct_amount_cents, reason, source_at_correction_id,
                   source_at_correction_document_kind,
                   source_at_correction_jurisdiction,
                   source_at_correction_concept,
                   source_at_correction_description,
                   source_at_correction_reported_amount_cents,
                   source_at_correction_determined_amount_cents,
                   source_at_correction_line_code, source_at_correction_source,
                   source_at_correction_source_version,
                   source_at_correction_document_hash, fingerprint
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id,
                tax_year,
                concept,
                revision_number,
                revision_kind,
                to_cents(correct_amount),
                reason,
                source.id,
                source.document_kind,
                source.jurisdiction,
                source.concept,
                source.description,
                to_cents(source.reported_amount) if source.reported_amount is not None else None,
                to_cents(source.determined_amount)
                if source.determined_amount is not None
                else None,
                source.line_code,
                source.source,
                source.source_version or None,
                source.document_hash or None,
                fingerprint,
            ),
        )
        if cursor.lastrowid is None:  # pragma: no cover
            raise RuntimeError("Correction revision was not created")
        return cursor.lastrowid

    def _required_by_id(self, revision_id: int) -> FactualCorrectionRevision:
        result = self.get_by_id(revision_id)
        if result is None:  # pragma: no cover
            raise RuntimeError("Correction revision was not found after insertion")
        return result

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[object, ...]) -> FactualCorrectionRevision:
        return FactualCorrectionRevision(
            id=CorrectionRepository._required_int(row[0]),
            person_id=CorrectionRepository._required_int(row[1]),
            tax_year=CorrectionRepository._required_int(row[2]),
            concept=str(row[3]),
            revision_number=CorrectionRepository._required_int(row[4]),
            revision_kind=str(row[5]),
            correct_amount=from_cents(row[6]) if row[6] is not None else None,
            reason=str(row[7]),
            source_at_correction_id=(
                CorrectionRepository._required_int(row[8]) if row[8] is not None else None
            ),
            source_document_kind=str(row[9]) if row[9] is not None else None,
            source_jurisdiction=str(row[10]) if row[10] is not None else None,
            source_concept=str(row[11]) if row[11] is not None else None,
            source_description=str(row[12]) if row[12] is not None else None,
            source_reported_amount=from_cents(row[13]) if row[13] is not None else None,
            source_determined_amount=from_cents(row[14]) if row[14] is not None else None,
            source_line_code=str(row[15]) if row[15] is not None else None,
            source_name=str(row[16]),
            source_version=str(row[17]) if row[17] is not None else None,
            source_document_hash=str(row[18]) if row[18] is not None else None,
            fingerprint=str(row[19]),
            created_at=str(row[20]),
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError("Correction revision identifier must be an integer")
        return value
