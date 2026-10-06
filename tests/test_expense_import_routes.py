# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""HTTP integration tests for expense-statement import."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import app as application
from infrastructure.runtime_config import RuntimeConfig
from repositories.expense_repository import ExpenseRepository
from repositories.person_repository import PersonRepository
from synthetic_documents import create_synthetic_hydro_qc_statement
from synthetic_runtime import create_synthetic_runtime


class ExpenseImportRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        runtime_directory = Path(self.temporary_directory.name) / "runtime"
        create_synthetic_runtime(runtime_directory)
        self.runtime = RuntimeConfig.load(runtime_directory)
        application.initialize(self.runtime)
        self.app = application.create_app(self.runtime)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-csrf-token"
        self.client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"
        self.statement = create_synthetic_hydro_qc_statement(
            runtime_directory / "synthetic-hydro.pdf"
        ).read_bytes()
        with self.runtime.connect() as connection:
            expense_repository = ExpenseRepository(connection)
            categories = expense_repository.list_categories()
            self.category_id = (
                categories[0].id
                if categories
                else expense_repository.create_category("Electricity", "required").id
            )
            people = PersonRepository(connection).list_all()
            self.person_id = people[0].id

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _confirm(self, *, filename: str = "hydro.pdf"):
        return self.client.post(
            "/api/expenses/import/confirm",
            data={
                "file": (io.BytesIO(self.statement), filename),
                "provider_key": "hydro-quebec",
                "name": "Home electricity",
                "category_id": str(self.category_id),
                "association": f"person:{self.person_id}",
                "period_start": "1900-01-01",
                "period_end": "2999-12-31",
            },
            content_type="multipart/form-data",
        )

    def test_preview_returns_exact_evidence_without_persisting(self) -> None:
        with self.runtime.connect() as connection:
            before = connection.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]

        response = self.client.post(
            "/api/expenses/import/preview",
            data={"file": (io.BytesIO(self.statement), "hydro.pdf")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()["preview"]
        self.assertEqual(preview["provider_key"], "hydro-quebec")
        self.assertEqual(preview["amount"], "31.00")
        self.assertEqual(preview["period_start"], "2026-01-01")
        self.assertEqual(preview["period_end"], "2026-01-31")
        with self.runtime.connect() as connection:
            after = connection.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0]
        self.assertEqual(after, before)

    def test_confirm_uses_parser_evidence_and_selected_association(self) -> None:
        response = self._confirm(filename="hydro-confirm.pdf")

        self.assertEqual(response.status_code, 201)
        record = response.get_json()
        self.assertEqual(record["amount"], "31.00")
        self.assertEqual(record["period_start"], "2026-01-01")
        self.assertEqual(record["period_end"], "2026-01-31")
        self.assertEqual(record["association_kind"], "person")
        self.assertEqual(record["association_id"], self.person_id)
        self.assertEqual(record["source_kind"], "imported")
        self.assertEqual(record["source_name"], "hydro-confirm.pdf")
        self.assertEqual(record["parser_name"], "hydro-quebec")
        self.assertTrue(record["source_hash"])

    def test_reimport_flags_overlapping_records(self) -> None:
        first = self._confirm()
        second = self._confirm()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json()["overlap_status"], "potential")
        with self.runtime.connect() as connection:
            statuses = connection.execute(
                "SELECT overlap_status FROM expense_records WHERE name = ?",
                ("Home electricity",),
            ).fetchall()
        self.assertEqual([row[0] for row in statuses], ["potential", "potential"])

    def test_malformed_or_mismatched_documents_return_400(self) -> None:
        response = self.client.post(
            "/api/expenses/import/confirm",
            data={
                "file": (io.BytesIO(b"not a supported PDF"), "wrong.pdf"),
                "provider_key": "hydro-quebec",
                "name": "Wrong",
                "category_id": str(self.category_id),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("does not match", response.get_json()["error"])

    def test_missing_file_returns_400(self) -> None:
        response = self.client.post("/api/expenses/import/preview", data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())


if __name__ == "__main__":
    unittest.main()
