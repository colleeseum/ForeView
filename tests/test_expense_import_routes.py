# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""HTTP integration tests for expense-statement import."""

from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import app as application
from devtools.synthetic.synthetic_documents import (
    create_synthetic_energir_statement,
    create_synthetic_hydro_qc_statement,
    create_synthetic_montreal_tax_statement,
)
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from expense_sources.registry import expense_source_registry
from infrastructure.runtime_config import RuntimeConfig
from ingestion.statement_import import content_hash
from repositories.expense_repository import ExpenseRepository
from repositories.person_repository import PersonRepository
from repositories.real_estate_asset_repository import RealEstateAssetRepository


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

    def test_icon_actions_preserve_escaped_payloads_and_localized_targets(self):
        class ActionParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.buttons = []
                self.unsafe = []

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == "button":
                    self.buttons.append(attributes)
                if tag in {"script", "img", "svg"} and (
                    "onerror" in attributes or "onload" in attributes
                ):
                    self.unsafe.append(attributes)

        name = "Synthetic 'quote' \"double\" & <img onerror=alert(1)>"
        category = self.client.post(
            "/api/expenses/categories", json={"name": name, "classification": "required"}
        ).get_json()
        record = self.client.post(
            "/api/expenses/manual",
            json={
                "name": name,
                "category_id": category["id"],
                "amount": "12.34",
                "period_start": "2026-02-01",
                "period_end": "2026-02-28",
            },
        ).get_json()
        imported = self._confirm(filename="Synthetic 'quotes' & file.pdf").get_json()
        localization = self.app.extensions["localization"]
        for locale in ("en-CA", "fr-CA"):
            with self.subTest(locale=locale):
                localization.select(locale)
                parser = ActionParser()
                parser.feed(self.client.get("/expenses?year=2026").text)
                self.assertFalse(parser.unsafe)
                edit = next(
                    button
                    for button in parser.buttons
                    if "data-expense-edit" in button
                    and json.loads(button["data-expense-edit"])["id"] == record["id"]
                )
                self.assertEqual(json.loads(edit["data-expense-edit"])["name"], name)
                self.assertEqual(edit["data-icon-action"], "edit")
                self.assertEqual(
                    edit["aria-label"],
                    localization.translate(locale, "browser.actions.edit", name=name),
                )
                category_edit = next(
                    button for button in parser.buttons if button.get("data-name") == name
                )
                self.assertEqual(category_edit["data-active"], "true")
                self.assertIn("data-category-edit", category_edit)
                delete = next(
                    button
                    for button in parser.buttons
                    if "data-expense-delete" in button
                    and json.loads(button["data-expense-delete"])["id"] == imported["id"]
                )
                payload = json.loads(delete["data-expense-delete"])
                self.assertEqual(payload["source_name"], "Synthetic 'quotes' & file.pdf")
                self.assertTrue(payload["expected_token"])
                self.assertEqual(delete["data-icon-action"], "delete")
                self.assertIn("fv-button--danger", delete["class"])
                self.assertEqual(
                    sum(button.get("data-icon-action") == "close" for button in parser.buttons), 6
                )

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

    def test_delete_excluded_duplicate_updates_totals_and_preserves_shared_provenance(self):
        first = self._confirm().get_json()
        duplicate = self._confirm().get_json()
        for record, include in ((first, True), (duplicate, False)):
            response = self.client.post(
                f"/api/expenses/{record['id']}/overlap",
                json={"include": include, "note": "Synthetic duplicate review"},
            )
            self.assertEqual(response.status_code, 200)
        records = self.client.get("/api/expenses").get_json()
        target = next(r for r in records if r["id"] == duplicate["id"])
        page = self.client.get("/expenses?year=2026").text
        self.assertIn("data-expense-delete=", page)
        response = self.client.delete(
            f"/api/expenses/{target['id']}", json={"expected_token": target["deletion_token"]}
        )
        self.assertEqual(response.status_code, 204)
        remaining = self.client.get("/api/expenses").get_json()
        self.assertNotIn(target["id"], [r["id"] for r in remaining])
        kept = next(r for r in remaining if r["id"] == first["id"])
        self.assertEqual(kept["overlap_status"], "clear")
        self.assertEqual(kept["source_hash"], first["source_hash"])
        with self.runtime.connect() as connection:
            self.assertIsNotNone(
                connection.execute(
                    "SELECT 1 FROM import_batches WHERE id = ?", (kept["source_document_id"],)
                ).fetchone()
            )
        repeated = self.client.delete(
            f"/api/expenses/{target['id']}", json={"expected_token": target["deletion_token"]}
        )
        self.assertEqual(repeated.status_code, 404)
        self.assertNotIn(f'"id": {target["id"]},', self.client.get("/api/expenses").text)

    def test_expense_deletion_requires_csrf_current_confirmation_for_all_sources(self):
        record = self._confirm().get_json()
        url = f"/api/expenses/{record['id']}"
        before = self.runtime.database_path.read_bytes()
        self.assertEqual(
            self.app.test_client()
            .delete(url, json={"expected_token": record["deletion_token"]})
            .status_code,
            403,
        )
        self.assertEqual(self.client.delete(url, json={}).status_code, 400)
        self.assertEqual(self.runtime.database_path.read_bytes(), before)
        for locale in ("en-CA", "fr-CA"):
            self.app.extensions["localization"].select(locale)
            response = self.client.delete(url, json={"expected_token": "stale"})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.get_json()["error_code"], "expense_delete_stale")
            self.assertEqual(response.get_json()["error_language"], locale)
            self.assertEqual(self.runtime.database_path.read_bytes(), before)
        manual = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Keep manual evidence",
                "category_id": self.category_id,
                "amount": "1.00",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        ).get_json()
        response = self.client.delete(
            f"/api/expenses/{manual['id']}", json={"expected_token": manual["deletion_token"]}
        )
        self.assertEqual(response.status_code, 204)
        self.assertNotIn(
            manual["id"], [record["id"] for record in self.client.get("/api/expenses").get_json()]
        )

    def test_failed_deletion_rolls_back_and_reused_id_cannot_delete_new_evidence(self):
        record = self._confirm().get_json()
        with self.runtime.connect() as connection:
            connection.execute(
                "CREATE TRIGGER reject_expense_cleanup BEFORE DELETE ON import_batches BEGIN SELECT RAISE(ABORT, 'Synthetic rejection'); END"
            )
            connection.commit()
        before = self.runtime.database_path.read_bytes()
        url = f"/api/expenses/{record['id']}"
        response = self.client.delete(url, json={"expected_token": record["deletion_token"]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.runtime.database_path.read_bytes(), before)
        with self.runtime.connect() as connection:
            connection.execute("DROP TRIGGER reject_expense_cleanup")
            connection.commit()
        self.assertEqual(
            self.client.delete(url, json={"expected_token": record["deletion_token"]}).status_code,
            204,
        )
        replacement = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Different evidence",
                "category_id": self.category_id,
                "amount": "1.00",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        ).get_json()
        self.assertEqual(replacement["id"], record["id"])
        self.assertEqual(
            self.client.delete(url, json={"expected_token": record["deletion_token"]}).status_code,
            409,
        )
        self.assertIn("Different evidence", self.client.get("/api/expenses").text)

    def test_main_help_topic_footer_actions_and_registry_sources_before_category_setup(self):
        for has_categories in (True, False):
            if not has_categories:
                with self.runtime.connect() as connection:
                    repository = ExpenseRepository(connection)
                    for category in repository.list_categories():
                        repository.set_category_active(category.id, False)
                    connection.commit()
            for locale in ("en-CA", "fr-CA"):
                with self.subTest(categories=has_categories, locale=locale):
                    self.app.extensions["localization"].select(locale)
                    before = self.runtime.database_path.read_bytes()
                    page = self.client.get("/expenses").text
                    dialog = page.split('id="expense-import-dialog-backdrop"', 1)[1].split(
                        "</dialog>", 1
                    )[0]
                    self.assertEqual(dialog.count('data-help-article="expense-import"'), 1)
                    self.assertNotIn("data-import-help", dialog)
                    self.assertNotIn("⟦", dialog)
                    footer = re.search(
                        r'<div class="dialog-actions fv-dialog-actions">(.*?)</div>', dialog, re.S
                    ).group(1)
                    self.assertLess(
                        footer.index('id="import-cancel"'), footer.index('id="import-confirm"')
                    )
                    if has_categories:
                        self.assertLess(
                            footer.index('id="import-cancel"'),
                            footer.index('id="import-preview-btn"'),
                        )
                        self.assertLess(
                            footer.index('id="import-preview-btn"'),
                            footer.index('id="import-confirm"'),
                        )
                    else:
                        self.assertNotIn('id="import-preview-btn"', dialog)
                        self.assertIn('id="import-open-categories"', dialog)
                    articles = self.client.get("/api/help").get_json()["articles"]
                    generic = next(a for a in articles if a["key"] == "expense-import")
                    self.assertEqual(generic["category"], "expense-imports")
                    self.assertEqual(generic["field_languages"]["body"], locale)
                    names = {
                        p.translations.get(locale, {}).get("display_name", p.display_name)
                        for p in expense_source_registry.providers
                    }
                    self.assertEqual(
                        {
                            line.removeprefix("• ")
                            for line in generic["body"].splitlines()
                            if line.startswith("• ")
                        },
                        names,
                    )
                    self.assertNotIn("{sources}", generic["body"])
                    self.assertIn(
                        "automatically detects" if locale == "en-CA" else "détecte automatiquement",
                        generic["body"],
                    )
                    self.assertEqual(
                        [a["key"] for a in articles if a["category"] == "expense-imports"],
                        ["expense-import"],
                    )
                    self.assertIn(
                        "request support" if locale == "en-CA" else "demander la prise en charge",
                        generic["body"],
                    )
                    self.assertEqual(self.runtime.database_path.read_bytes(), before)

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

    def _montreal_import(self, content, *, name="Municipal tax", association="household"):
        return self.client.post(
            "/api/expenses/import/confirm",
            data={
                "file": (io.BytesIO(content), "synthetic-municipal-tax.pdf"),
                "provider_key": "montreal-tax",
                "name": name,
                "category_id": str(self.category_id),
                "association": association,
                "amount": "1.00",
                "period_start": "1900-01-01",
                "period_end": "1900-12-31",
                "period_kind": "recurring_statement",
            },
        )

    def test_montreal_annual_obligation_preview_confirm_property_and_provenance(self):
        content = create_synthetic_montreal_tax_statement(
            self.runtime.data_dir / "tax.pdf"
        ).read_bytes()
        with self.runtime.connect() as connection:
            self.category_id = (
                ExpenseRepository(connection)
                .create_category("Synthetic municipal tax", "required")
                .id
            )
            asset = RealEstateAssetRepository(connection).create(
                "Synthetic test property", Decimal("500000.00"), "2026-01-01"
            )
            connection.commit()
        before = self.runtime.database_path.read_bytes()
        response = self.client.post(
            "/api/expenses/import/preview", data={"file": (io.BytesIO(content), "tax.pdf")}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.runtime.database_path.read_bytes(), before)
        preview = response.get_json()["preview"]
        self.assertEqual(preview["provider_key"], "montreal-tax")
        self.assertIn("123 Example Street", preview["suggested_identity"])
        self.assertNotIn("Alex Example", preview["suggested_identity"])
        record_response = self._montreal_import(content, association=f"real_estate:{asset.id}")
        self.assertEqual(record_response.status_code, 201)
        record = record_response.get_json()
        self.assertEqual(record["name"], "Municipal tax")
        self.assertEqual(record["amount"], "4000.03")
        self.assertEqual(record["period_start"], "2026-01-01")
        self.assertEqual(record["period_end"], "2026-12-31")
        self.assertEqual(record["period_kind"], "annual_or_one_time")
        self.assertEqual(record["category_id"], self.category_id)
        self.assertEqual(record["association_kind"], "real_estate")
        self.assertEqual(record["association_id"], asset.id)
        self.assertEqual(record["source_hash"], content_hash(content))
        self.assertEqual(record["parser_name"], "montreal-tax")
        self.assertEqual(record["parser_version"], "2026.10.28")
        with self.runtime.connect() as connection:
            category = next(
                c
                for c in ExpenseRepository(connection).totals_for_year(2026)["categories"]
                if c["category_id"] == self.category_id
            )
            self.assertEqual(category["amount"], Decimal("4000.03"))
            # An annual obligation never becomes a recurring seasonal estimate.
            self.assertEqual(category["annualized_estimate"], Decimal("4000.03"))
            self.assertEqual(
                RealEstateAssetRepository(connection).get(asset.id).estimated_value,
                asset.estimated_value,
            )

    def test_montreal_annual_bill_and_manual_installment_require_overlap_review(self):
        content = create_synthetic_montreal_tax_statement(
            self.runtime.data_dir / "tax.pdf"
        ).read_bytes()
        with self.runtime.connect() as connection:
            manual = ExpenseRepository(connection).create_manual_expense(
                name="Municipal tax",
                category_id=self.category_id,
                amount=Decimal("2000.01"),
                period_start=date(2026, 3, 2),
                period_end=date(2026, 3, 2),
            )
            connection.commit()
        response = self._montreal_import(content)
        self.assertEqual(response.status_code, 201)
        annual = response.get_json()
        self.assertEqual(annual["overlap_status"], "potential")
        with self.runtime.connect() as connection:
            self.assertEqual(
                ExpenseRepository(connection).totals_for_year(2026)["status"], "needs_resolution"
            )
        for id, include in ((manual.id, False), (annual["id"], True)):
            result = self.client.post(
                f"/api/expenses/{id}/overlap",
                json={
                    "include": include,
                    "note": "Annual obligation retained; installment is not extra spending",
                },
            )
            self.assertEqual(result.status_code, 200)
        duplicate = self._montreal_import(content, name="Renamed municipal tax")
        self.assertEqual(duplicate.status_code, 201)
        self.assertEqual(duplicate.get_json()["overlap_status"], "potential")

    def test_montreal_invalid_amounts_create_no_facts_and_localize(self):
        content = create_synthetic_montreal_tax_statement(
            self.runtime.data_dir / "bad-tax.pdf", total="4 000,04"
        ).read_bytes()
        for locale in ("en-CA", "fr-CA"):
            self.app.extensions["localization"].select(locale)
            before = self.runtime.database_path.read_bytes()
            for path in ("/api/expenses/import/preview", "/api/expenses/import/confirm"):
                response = self.client.post(
                    path,
                    data={
                        "file": (io.BytesIO(content), "invalid-tax.pdf"),
                        "provider_key": "montreal-tax",
                        "name": "Invalid tax",
                        "category_id": str(self.category_id),
                    },
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error_code"], "expense_montreal_amount")
                self.assertEqual(response.get_json()["error_language"], locale)
                self.assertEqual(self.runtime.database_path.read_bytes(), before)

    def test_montreal_french_and_english_copies_share_identity_and_require_overlap_review(self):
        ids = []
        identity = None
        for source_language, locale in (("en", "fr-CA"), ("fr", "en-CA")):
            self.app.extensions["localization"].select(locale)
            content = create_synthetic_montreal_tax_statement(
                self.runtime.data_dir / f"tax-{source_language}.pdf", language=source_language
            ).read_bytes()
            before = self.runtime.database_path.read_bytes()
            response = self.client.post(
                "/api/expenses/import/preview",
                data={"file": (io.BytesIO(content), f"tax-{source_language}.pdf")},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.runtime.database_path.read_bytes(), before)
            preview = response.get_json()["preview"]
            identity = identity or preview["suggested_identity"]
            self.assertEqual(preview["suggested_identity"], identity)
            self.assertEqual(preview["provider_display_language"], locale)
            response = self._montreal_import(content, name=identity)
            self.assertEqual(response.status_code, 201)
            record = response.get_json()
            self.assertEqual(record["amount"], "4000.03")
            self.assertEqual(record["period_kind"], "annual_or_one_time")
            ids.append(record["id"])
        with self.runtime.connect() as connection:
            repository = ExpenseRepository(connection)
            first, second = (repository.get_expense(id) for id in ids)
            self.assertEqual(first.identity_id, second.identity_id)
            self.assertNotEqual(first.source_hash, second.source_hash)
            self.assertEqual(
                [first.overlap_status, second.overlap_status], ["potential", "potential"]
            )
            self.assertEqual(repository.totals_for_year(2026)["status"], "needs_resolution")

    def test_montreal_help_and_preview_are_translated_without_changing_source_identity(self):
        content = create_synthetic_montreal_tax_statement(
            self.runtime.data_dir / "tax.pdf"
        ).read_bytes()
        for locale in ("en-CA", "fr-CA"):
            self.app.extensions["localization"].select(locale)
            response = self.client.post(
                "/api/expenses/import/preview", data={"file": (io.BytesIO(content), "tax.pdf")}
            )
            self.assertEqual(response.status_code, 200)
            preview = response.get_json()["preview"]
            self.assertEqual(preview["provider_display_language"], locale)
            self.assertEqual(preview["amount"], "4000.03")
            self.assertIn("000001-00", preview["suggested_identity"])
            articles = self.client.get("/api/help").get_json()["articles"]
            article = next(a for a in articles if a["key"] == "expense-import")
            self.assertEqual(article["field_languages"]["body"], locale)
            self.assertIn("Montréal", article["body"])

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
        source = next(article for article in articles if article["key"] == "expense-import")
        self.assertEqual(source["category"], "expense-imports")
        self.assertIn("Énergir", source["body"])
        self.assertEqual(source["field_languages"]["body"], "fr-CA")


if __name__ == "__main__":
    unittest.main()
