# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Service tests for expense-statement preview and confirmation."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from ingestion.statement_import import content_hash
from repositories.expense_repository import ExpenseRepository
from repositories.import_batch_repository import ImportBatchRepository
from services.database_initialization import ensure_domain_schema
from services.expense_import_service import ExpenseImportService
from synthetic_documents import create_synthetic_hydro_qc_statement
from tests.support import create_person


class ExpenseImportServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        ensure_domain_schema(self.connection)
        self.expenses = ExpenseRepository(self.connection)
        self.category = self.expenses.create_category("Electricity", "required")
        self.person_id = create_person(self.connection, "Synthetic Resident")
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = create_synthetic_hydro_qc_statement(
            Path(self.temporary_directory.name) / "hydro.pdf"
        )
        self.content = self.path.read_bytes()
        self.service = ExpenseImportService(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_preview_returns_exact_evidence_without_persistence(self) -> None:
        preview = self.service.preview(self.content, source_filename="hydro.pdf")

        self.assertEqual(preview.provider_key, "hydro-quebec")
        self.assertEqual(preview.amount, Decimal("31.00"))
        self.assertEqual(preview.period_start, date(2026, 1, 1))
        self.assertEqual(preview.period_end, date(2026, 1, 31))
        self.assertEqual(preview.to_dict()["amount"], "31.00")
        self.assertEqual(ImportBatchRepository(self.connection).history(), [])
        self.assertEqual(self.expenses.list_expenses(), [])

    def test_confirm_persists_exact_amount_dates_association_and_provenance(self) -> None:
        record = self.service.confirm(
            content=self.content,
            source_filename="hydro.pdf",
            provider_key="hydro-quebec",
            name="Home electricity",
            category_id=self.category.id,
            association_kind="person",
            association_id=self.person_id,
        )

        self.assertEqual(record.amount, Decimal("31.00"))
        self.assertEqual(record.period_start, "2026-01-01")
        self.assertEqual(record.period_end, "2026-01-31")
        self.assertEqual(record.association_kind, "person")
        self.assertEqual(record.association_id, self.person_id)
        self.assertEqual(record.source_kind, "imported")
        self.assertEqual(record.source_name, "hydro.pdf")
        self.assertEqual(record.parser_name, "hydro-quebec")
        self.assertEqual(record.source_hash, content_hash(self.content))
        batch = ImportBatchRepository(self.connection).get_by_hash(content_hash(self.content))
        self.assertIsNotNone(batch)
        self.assertEqual(batch.row_count, 1)

    def test_confirm_rejects_document_that_does_not_match_selected_provider(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match the expected format"):
            self.service.confirm(
                content=b"not a Hydro PDF",
                source_filename="wrong.pdf",
                provider_key="hydro-quebec",
                name="Home electricity",
                category_id=self.category.id,
            )

    def test_reimport_creates_overlap_for_review_instead_of_double_counting(self) -> None:
        arguments = {
            "content": self.content,
            "source_filename": "hydro.pdf",
            "provider_key": "hydro-quebec",
            "name": "Home electricity",
            "category_id": self.category.id,
        }
        first = self.service.confirm(**arguments)
        second = self.service.confirm(**arguments)

        self.assertEqual(second.overlap_status, "potential")
        self.assertEqual(self.expenses.get_expense(first.id).overlap_status, "potential")
        self.assertEqual(self.expenses.totals_for_year(2026)["status"], "needs_resolution")

        unrelated = self.expenses.create_manual_expense(
            name="Internet",
            category_id=self.category.id,
            amount="80.00",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
        )
        self.expenses.update_expense(
            unrelated.id,
            name="Internet service",
            category_id=self.category.id,
            amount="80.00",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
        )

        self.assertEqual(self.expenses.get_expense(first.id).overlap_status, "potential")
        self.assertEqual(self.expenses.get_expense(second.id).overlap_status, "potential")
        self.assertEqual(self.expenses.totals_for_year(2026)["status"], "needs_resolution")

    def test_reimport_with_edited_identity_still_requires_duplicate_review(self) -> None:
        other_category = self.expenses.create_category("Cottage electricity", "required")
        first = self.service.confirm(
            content=self.content,
            source_filename="hydro.pdf",
            provider_key="hydro-quebec",
            name="Home electricity",
            category_id=self.category.id,
        )

        second = self.service.confirm(
            content=self.content,
            source_filename="renamed.pdf",
            provider_key="hydro-quebec",
            name="Cottage power",
            category_id=other_category.id,
            association_kind="person",
            association_id=self.person_id,
        )

        self.assertEqual(second.overlap_status, "potential")
        self.assertEqual(self.expenses.get_expense(first.id).overlap_status, "potential")
        self.assertEqual(self.expenses.totals_for_year(2026)["status"], "needs_resolution")

    def test_failed_confirmation_rolls_back_import_batch(self) -> None:
        with self.assertRaisesRegex(LookupError, "not found"):
            self.service.confirm(
                content=self.content,
                source_filename="hydro.pdf",
                provider_key="hydro-quebec",
                name="Home electricity",
                category_id=99999,
            )

        self.assertIsNone(
            ImportBatchRepository(self.connection).get_by_hash(content_hash(self.content))
        )


if __name__ == "__main__":
    unittest.main()
