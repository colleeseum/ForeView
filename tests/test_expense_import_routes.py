# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""HTTP integration tests for expense-statement import."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import app as application
from devtools.synthetic.synthetic_documents import (
    create_synthetic_energir_statement,
    create_synthetic_hydro_qc_statement,
)
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from infrastructure.runtime_config import RuntimeConfig
from ingestion.statement_import import content_hash
from repositories.expense_repository import ExpenseRepository
from repositories.person_repository import PersonRepository


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

    def test_energir_preview_confirm_provenance_and_tampered_client_fields(self):
        content = create_synthetic_energir_statement(
            self.runtime.data_dir / "synthetic-gas.pdf"
        ).read_bytes()
        before = self.runtime.database_path.read_bytes()
        preview = self.client.post(
            "/api/expenses/import/preview", data={"file": (io.BytesIO(content), "gas.pdf")}
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(self.runtime.database_path.read_bytes(), before)
        evidence = preview.get_json()["preview"]
        self.assertEqual(evidence["provider_key"], "energir")
        self.assertEqual(evidence["amount"], "114.98")
        self.assertEqual(evidence["period_start"], "2025-12-15")
        self.assertEqual(evidence["period_end"], "2026-01-14")
        self.assertEqual(evidence["period_kind"], "recurring_statement")
        response = self.client.post(
            "/api/expenses/import/confirm",
            data={
                "file": (io.BytesIO(content), "gas.pdf"),
                "provider_key": "energir",
                "name": "User chosen gas identity",
                "category_id": str(self.category_id),
                "association": f"person:{self.person_id}",
                "amount": "999999.99",
                "period_start": "1900-01-01",
                "period_end": "1900-12-31",
            },
        )
        self.assertEqual(response.status_code, 201)
        record = response.get_json()
        for key in ("amount", "period_start", "period_end", "period_kind"):
            self.assertEqual(record[key], evidence[key])
        self.assertEqual(record["name"], "User chosen gas identity")
        self.assertEqual(record["category_id"], self.category_id)
        self.assertEqual(record["association_id"], self.person_id)
        self.assertEqual(record["association_kind"], "person")
        self.assertEqual(record["source_kind"], "imported")
        self.assertEqual(record["parser_name"], "energir")
        self.assertEqual(record["parser_version"], "2026.10.28")
        self.assertEqual(record["source_hash"], content_hash(content))

    def test_energir_reimport_with_different_identity_is_not_silently_counted(self):
        content = create_synthetic_energir_statement(
            self.runtime.data_dir / "synthetic-gas.pdf"
        ).read_bytes()
        ids = []
        for name in ("First gas identity", "Renamed gas identity"):
            response = self.client.post(
                "/api/expenses/import/confirm",
                data={
                    "file": (io.BytesIO(content), f"{name}.pdf"),
                    "provider_key": "energir",
                    "name": name,
                    "category_id": str(self.category_id),
                    "association": "household",
                },
            )
            self.assertEqual(response.status_code, 201)
            ids.append(response.get_json()["id"])
        with self.runtime.connect() as connection:
            records = [ExpenseRepository(connection).get_expense(id) for id in ids]
            self.assertEqual(
                [record.overlap_status for record in records], ["potential", "potential"]
            )
            self.assertEqual(
                ExpenseRepository(connection).totals_for_year(2026)["status"], "needs_resolution"
            )
        for id, include in zip(ids, (True, False), strict=True):
            resolved = self.client.post(
                f"/api/expenses/{id}/overlap",
                json={"include": include, "note": "Synthetic duplicate reviewed"},
            )
            self.assertEqual(resolved.status_code, 200)

    def test_energir_unsupported_bills_localize_and_create_no_facts(self):
        content = create_synthetic_energir_statement(
            self.runtime.data_dir / "synthetic-gas-mpe.pdf", front_note="Mode de paiements égaux"
        ).read_bytes()
        for locale in ("en-CA", "fr-CA"):
            self.app.extensions["localization"].select(locale)
            before = self.runtime.database_path.read_bytes()
            for path in ("/api/expenses/import/preview", "/api/expenses/import/confirm"):
                response = self.client.post(
                    path,
                    data={
                        "file": (io.BytesIO(content), "unsupported.pdf"),
                        "provider_key": "energir",
                        "name": "Should not exist",
                        "category_id": str(self.category_id),
                    },
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error_code"], "expense_energir_unsupported")
                self.assertEqual(response.get_json()["error_language"], locale)
                self.assertEqual(self.runtime.database_path.read_bytes(), before)
        self.assertEqual(
            self.app.test_client()
            .post(
                "/api/expenses/import/preview", data={"file": (io.BytesIO(content), "no-csrf.pdf")}
            )
            .status_code,
            403,
        )

    def test_energir_help_is_discovered_and_translated(self):
        self.app.extensions["localization"].select("fr-CA")
        content = create_synthetic_energir_statement(
            self.runtime.data_dir / "synthetic-gas-fr.pdf"
        ).read_bytes()
        response = self.client.post(
            "/api/expenses/import/preview", data={"file": (io.BytesIO(content), "gas-fr.pdf")}
        )
        self.assertEqual(response.status_code, 200)
        preview = response.get_json()["preview"]
        self.assertEqual(preview["provider_display_name"], "Facture de gaz naturel d’Énergir")
        self.assertEqual(preview["provider_display_language"], "fr-CA")
        articles = self.client.get("/api/help").get_json()["articles"]
        source = next(article for article in articles if article["key"] == "expense-source-energir")
        self.assertEqual(source["category"], "expense-imports")
        self.assertIn("Énergir", source["title"])
        self.assertEqual(source["field_languages"]["body"], "fr-CA")


if __name__ == "__main__":
    unittest.main()
