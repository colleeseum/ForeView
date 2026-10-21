# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import io
import json
import re
import shutil
import sqlite3
import tempfile
import unittest
import urllib.error
from contextlib import closing
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as application
from devtools.synthetic.synthetic_questrade import SyntheticQuestradeAPI
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from domain.parsed_public_pension_statement import ParsedPublicPensionStatement
from domain.parsed_tax_assessment import ParsedTaxAssessment
from domain.parsed_tax_value import ParsedTaxValue
from domain.parsed_ufile_tax_return import ParsedUFileTaxReturn
from domain.validation_error import ValidationError
from infrastructure.runtime_config import RuntimeConfig
from institution_support.help_topic import HelpTopic
from institutions.questrade.client import QuestradeClient
from institutions.questrade.connection import QuestradeConnectionProvider
from institutions.questrade.settings import AUTHORIZE_URL, TOKEN_URL, QuestradeSettings
from institutions.questrade.unauthorized import QuestradeUnauthorized
from localization import LocalizationService
from repositories.person_repository import PersonRepository
from repositories.public_rule_approval_repository import PublicRuleApprovalRepository
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from repositories.real_estate_asset_repository import RealEstateAssetRepository
from repositories.real_estate_projection_repository import RealEstateProjectionRepository
from repositories.scenario_assumption_repository import ScenarioAssumptionRepository
from services.projections.public_rule_catalog import PublicRuleCatalog


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temporary_directory.name) / "runtime"
        self.database, _ = create_synthetic_runtime(self.runtime)
        self._use_runtime(RuntimeConfig.load(self.runtime))

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _use_runtime(self, runtime):
        self.runtime_config = runtime
        application.initialize(runtime)
        self.app = application.create_app(runtime)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-csrf-token"
        self.client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"

    def _people(self):
        response = self.client.get("/api/model/people")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["people"]

    @staticmethod
    def _visible_html(response):
        return re.sub(
            rb'<script id="browser-localization"[^>]*>.*?</script>',
            b"",
            response.data,
            flags=re.DOTALL,
        )

    def test_account_api_exposes_registered_account_type_contract(self):
        response = self.client.get("/api/model/accounts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["key"] for item in response.get_json()["account_types"]],
            ["non_registered", "resp", "rrsp", "tfsa"],
        )

    def _questrade(self):
        return application.connection_providers(self.runtime_config)["questrade"]

    def _serving(self, runtime):
        """Serve requests from another configuration of the same runtime folder."""
        return patch.dict(self.app.extensions, {"finance_runtime": runtime})

    def _questrade_logins(self, *names):
        logins = [
            {"name": name, "consumer_key": "synthetic-key", "client_secret": ""} for name in names
        ]
        return self._serving(self.runtime_config.with_values(QUESTRADE_CONNECTIONS=logins))

    @staticmethod
    def _stored_authorization(connection, name="alex"):
        return QuestradeAuthorizationRepository(connection).get_by_name(name)

    def test_about_page_localization_and_language_metadata(self):
        localization = self.app.extensions["localization"]
        for code, heading in (("en-CA", "About"), ("fr-CA", "À propos")):
            with self.subTest(locale=code):
                localization.select(code)
                response = self.client.get("/about")
                self.assertEqual(response.status_code, 200)
                text = unescape(self._visible_html(response).decode("utf-8"))
                self.assertIn(f'<html lang="{code}" dir="ltr">', text)
                self.assertIn(
                    f"<h1>{localization.translate(code, 'pages_server.about.heading')}</h1>",
                    text,
                )
                self.assertIn(
                    f"<p>{localization.translate(code, 'pages_server.about.description')}</p>",
                    text,
                )
                self.assertNotIn("⟦", text)
                self.assertIn(heading, text)

    def test_locale_navigation_persistence_rtl_and_financial_invariance(self):
        catalog_root = Path(self.temporary_directory.name) / "localization"
        shutil.copytree(application.ROOT / "localization", catalog_root)
        registry_path = catalog_root / "registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["locales"].append(
            {
                "code": "ar-XB",
                "native_name": "Synthetic RTL",
                "direction": "rtl",
                "fallback": "fr-CA",
            }
        )
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        rtl_catalog = catalog_root / "ar-XB"
        rtl_catalog.mkdir()
        (rtl_catalog / "core.json").write_text(
            json.dumps({"nav": {"summary": "RTL summary"}}), encoding="utf-8"
        )
        self.app.extensions["localization"] = LocalizationService(catalog_root, self.runtime)
        api_paths = (
            "/api/dashboard",
            "/api/model/accounts",
            "/api/model/people",
            "/api/model/import-history",
        )
        before = {path: self.client.get(path).get_json() for path in api_paths}
        database_before = self.database.read_bytes()
        for locale, direction in (("en-CA", "ltr"), ("fr-CA", "ltr"), ("ar-XB", "rtl")):
            with self.subTest(locale=locale):
                selected = self.client.post(
                    "/application-settings/language", data={"locale": locale}, follow_redirects=True
                )
                self.assertEqual(selected.status_code, 200)
                # Recreate the service to exercise persisted preference, not its in-memory state.
                self.app.extensions["localization"] = LocalizationService(
                    catalog_root, self.runtime
                )
                self.assertEqual(self.app.extensions["localization"].selected_locale(), locale)
                for path in (
                    "/",
                    "/setup",
                    "/accounts",
                    "/income",
                    "/transactions",
                    "/connections",
                    "/expenses",
                    "/salary-projection",
                    "/about",
                    "/disclaimer",
                ):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    html = response.get_data(as_text=True)
                    self.assertIn(f'<html lang="{locale}" dir="{direction}">', html)
                    self.assertNotIn("⟦", self._visible_html(response).decode("utf-8"))
                if locale == "ar-XB":
                    page = self.client.get("/").get_data(as_text=True)
                    self.assertIn("RTL summary", page)
                    self.assertIn("Données financières", page)
                    match = re.search(
                        r'<script id="browser-localization"[^>]*>(.*?)</script>', page, re.S
                    )
                    self.assertIsNotNone(match)
                    state = json.loads(match.group(1))
                    self.assertEqual(state["fallbacks"], ["fr-CA", "en-CA"])
                    self.assertEqual(set(state["catalogs"]), {"ar-XB", "fr-CA", "en-CA"})
                disclaimer = self.client.get("/disclaimer").get_data(as_text=True)
                self.assertIn('legal-document" lang="en-CA" dir="ltr"', disclaimer)
                self.assertEqual(
                    {path: self.client.get(path).get_json() for path in api_paths}, before
                )
                self.assertEqual(self.database.read_bytes(), database_before)

    def test_setup_examples_and_invalid_language_submission_are_localized(self):
        for locale, person, gic in (
            ("en-CA", "Alex Example", "RBC GIC 1"),
            ("fr-CA", "Alex Exemple", "RBC CPG 1"),
        ):
            self.app.extensions["localization"].select(locale)
            html = self.client.get("/setup").get_data(as_text=True)
            self.assertIn(f'placeholder="{person}"', html)
            self.assertIn(f'placeholder="{gic}"', html)
            response = self.client.post(
                "/application-settings/language", data={"locale": "unknown"}
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.get_data(as_text=True),
                self.app.extensions["localization"].translate(
                    locale, "pages_server.setup.unsupported_locale"
                ),
            )
            self.assertEqual(self.app.extensions["localization"].selected_locale(), locale)

    def test_request_validation_messages_have_localized_text_and_stable_codes(self):
        cases = (
            ("GET", "/api/income", "person_required"),
            ("POST", "/api/income/import/preview", "income_pdf_required"),
            ("POST", "/api/expenses/import/preview", "expense_pdf_required"),
            ("POST", "/api/expenses/import/confirm", "expense_pdf_required"),
            ("GET", "/api/salary-projection?start_year=2026&end_year=2025", "projection_range"),
            ("PUT", "/api/salary-projection/scenarios/1/people/1/overrides", "overrides_list"),
        )
        for locale in ("en-CA", "fr-CA"):
            self.app.extensions["localization"].select(locale)
            for method, path, code in cases:
                with self.subTest(locale=locale, path=path):
                    response = self.client.open(path, method=method, json={})
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(
                        response.get_json(),
                        {
                            "error": self.app.extensions["localization"].translate(
                                locale, f"errors.{code}"
                            ),
                            "error_code": code,
                            "error_language": locale,
                        },
                    )

    def test_provider_import_buttons_localize_without_changing_source_metadata(self):
        self.app.extensions["localization"].select("fr-CA")
        income = unescape(self.client.get("/income").get_data(as_text=True))
        expenses = unescape(self.client.get("/expenses").get_data(as_text=True))
        self.assertIn('<span lang="fr-CA">PDF T1 UFile</span>', income)
        self.assertIn('<span lang="fr-CA">Avis de cotisation de l’ARC</span>', income)
        self.assertIn('<span lang="fr-CA">Facture d’électricité d’Hydro-Québec</span>', expenses)
        source = self.client.get("/api/income/sources").get_json()["sources"][0]
        self.assertEqual(source["display_name"], "UFile T1 PDF")
        self.assertEqual(source["presentation"]["display_name"], "PDF T1 UFile")
        self.assertNotEqual(source["presentation"]["help_text"], source["help_text"])
        self.assertIn("How to download", source["help_text"])
        self.assertEqual(source["presentation"]["field_languages"]["help_text"], "fr-CA")

    def test_correction_workflow_in_both_locales_preserves_underlying_facts(self):
        person_id = self._people()[0]["id"]
        for locale, year in (("en-CA", 2028), ("fr-CA", 2029)):
            with self.subTest(locale=locale):
                localization = self.app.extensions["localization"]
                localization.select(locale)
                saved = self.client.put(
                    f"/api/income/people/{person_id}/years/{year}",
                    json={
                        "employment_income": "100000",
                        "province_of_residence": "QC",
                        "source": "Original English evidence",
                    },
                )
                self.assertEqual(saved.status_code, 200)
                underlying = saved.get_json()
                payload = {
                    "person_id": person_id,
                    "tax_year": year,
                    "concept": "employment_income",
                    "correct_amount": "110000",
                    "reason": "Supporting English records",
                    "expected_revision": 0,
                }
                invalid = self.client.post(
                    "/api/income/corrections", json={**payload, "reason": " "}
                )
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(
                    invalid.get_json(),
                    {
                        "error": localization.translate(
                            locale, "errors.correction_reason_required"
                        ),
                        "error_code": "correction_reason_required",
                        "error_language": locale,
                    },
                )
                created_response = self.client.post("/api/income/corrections", json=payload)
                self.assertEqual(created_response.status_code, 201)
                created = created_response.get_json()
                path = f"/api/income/corrections/{created['id']}"
                edited_response = self.client.put(
                    path,
                    json={
                        "correct_amount": "115000",
                        "reason": "Revised English records",
                        "expected_revision": 1,
                    },
                )
                self.assertEqual(edited_response.status_code, 200)
                edited = edited_response.get_json()
                stale = self.client.put(
                    path,
                    json={
                        "correct_amount": "120000",
                        "reason": "Stale input",
                        "expected_revision": 1,
                    },
                )
                self.assertEqual(stale.status_code, 409)
                self.assertEqual(stale.get_json()["error_code"], "correction_stale")
                self.assertEqual(stale.get_json()["error_language"], locale)
                confirmed = self.client.post(
                    f"/api/income/corrections/{edited['id']}/confirm", json={"expected_revision": 2}
                )
                self.assertEqual(confirmed.status_code, 200)
                removed = self.client.delete(
                    f"/api/income/corrections/{confirmed.get_json()['id']}",
                    json={"expected_revision": 3},
                )
                self.assertEqual(removed.status_code, 200)
                history = self.client.get(
                    f"/api/income/corrections/person/{person_id}/year/{year}/employment_income"
                ).get_json()["corrections"]
                self.assertEqual(len(history), 4)
                self.assertEqual(history[0]["reason"], "Supporting English records")
                self.assertEqual(
                    self.client.get(f"/api/income?person_id={person_id}&year={year}").get_json()[
                        "record"
                    ],
                    underlying,
                )
                missing = self.client.delete(
                    "/api/income/corrections/999999", json={"expected_revision": 1}
                )
                self.assertEqual(missing.status_code, 404)
                self.assertEqual(missing.get_json()["error_code"], "correction_not_found")
                self.assertEqual(missing.get_json()["error_language"], locale)

    def test_expense_validation_and_overlap_workflow_in_both_locales(self):
        for locale, year in (("en-CA", 2028), ("fr-CA", 2029)):
            with self.subTest(locale=locale):
                localization = self.app.extensions["localization"]
                localization.select(locale)
                category_response = self.client.post(
                    "/api/expenses/categories",
                    json={
                        "name": f"Original English category {year}",
                        "classification": "required",
                    },
                )
                self.assertEqual(category_response.status_code, 201)
                category_id = category_response.get_json()["id"]
                payload = {
                    "name": "Original English electricity",
                    "category_id": category_id,
                    "amount": "125.50",
                    "period_start": f"{year}-01-01",
                    "period_end": f"{year}-01-31",
                }
                cases = (
                    (
                        "/api/expenses/categories",
                        {"name": "", "classification": "required"},
                        "expense_category_name",
                    ),
                    (
                        "/api/expenses/categories",
                        {"name": "Original", "classification": "unknown"},
                        "expense_classification",
                    ),
                    (
                        "/api/expenses/manual",
                        {**payload, "amount": "NaN"},
                        "expense_amount_invalid",
                    ),
                    (
                        "/api/expenses/manual",
                        {**payload, "amount": "-1"},
                        "expense_amount_negative",
                    ),
                    (
                        "/api/expenses/manual",
                        {**payload, "period_end": "not-a-date"},
                        "expense_date",
                    ),
                    (
                        "/api/expenses/manual",
                        {**payload, "period_start": f"{year}-02-01"},
                        "expense_period_order",
                    ),
                    (
                        "/api/expenses/manual",
                        {**payload, "association_kind": "person", "association_id": 999999},
                        "expense_association_missing",
                    ),
                    (
                        "/api/expenses/manual",
                        {**payload, "category_id": 999999},
                        "expense_category_missing",
                    ),
                    (
                        "/api/expenses/manual",
                        {**payload, "category_id": float("inf")},
                        "expense_integer",
                    ),
                )
                for path, invalid_payload, code in cases:
                    before = self.database.read_bytes()
                    invalid = self.client.post(path, json=invalid_payload)
                    self.assertEqual(invalid.status_code, 400)
                    self.assertEqual(invalid.get_json()["error_code"], code)
                    self.assertEqual(invalid.get_json()["error_language"], locale)
                    self.assertEqual(self.database.read_bytes(), before)
                before = self.database.read_bytes()
                bad_update = self.client.put(
                    f"/api/expenses/categories/{category_id}",
                    json={
                        "name": "Uncommitted name change",
                        "classification": "unknown",
                        "active": True,
                    },
                )
                self.assertEqual(bad_update.status_code, 400)
                self.assertEqual(bad_update.get_json()["error_code"], "expense_classification")
                self.assertEqual(self.database.read_bytes(), before)
                form = self.client.post(
                    "/expenses/categories",
                    data={"name": "", "classification": "required", "year": year},
                    follow_redirects=True,
                )
                self.assertEqual(form.status_code, 200)
                html = unescape(form.get_data(as_text=True))
                self.assertIn(
                    f'lang="{locale}" role="alert">{localization.translate(locale, "errors.expense_category_name")}',
                    html,
                )
                first = self.client.post("/api/expenses/manual", json=payload)
                second = self.client.post("/api/expenses/manual", json=payload)
                self.assertEqual(first.status_code, 201)
                self.assertEqual(second.status_code, 201)
                first_id, second_id = first.get_json()["id"], second.get_json()["id"]
                before = self.database.read_bytes()
                bad_note = self.client.post(
                    f"/api/expenses/{first_id}/overlap", json={"include": True, "note": " "}
                )
                self.assertEqual(bad_note.get_json()["error_code"], "expense_overlap_note")
                self.assertEqual(self.database.read_bytes(), before)
                for record_id, include in ((first_id, True), (second_id, False)):
                    resolved = self.client.post(
                        f"/api/expenses/{record_id}/overlap",
                        json={"include": include, "note": "Original English audit note"},
                    )
                    self.assertEqual(resolved.status_code, 200)
                    self.assertEqual(
                        resolved.get_json()["overlap_resolution_note"],
                        "Original English audit note",
                    )
                records = self.client.get(f"/api/expenses?year={year}").get_json()
                self.assertEqual(
                    {row["overlap_status"] for row in records},
                    {"resolved_include", "resolved_exclude"},
                )
                self.assertTrue(all(row["name"] == payload["name"] for row in records))
                before = self.database.read_bytes()
                unsupported = self.client.post(
                    "/api/expenses/import/preview",
                    data={
                        "file": (io.BytesIO(b"Unsupported synthetic document"), "unsupported.pdf")
                    },
                )
                self.assertEqual(unsupported.status_code, 400)
                self.assertEqual(unsupported.get_json()["error_code"], "expense_source_unsupported")
                self.assertEqual(unsupported.get_json()["error_language"], locale)
                self.assertEqual(self.database.read_bytes(), before)
                with patch(
                    "web.expense_routes.ExpenseImportService.preview",
                    side_effect=KeyError("External parser detail"),
                ):
                    diagnostic = self.client.post(
                        "/api/expenses/import/preview",
                        data={"file": (io.BytesIO(b"Synthetic"), "external.pdf")},
                    )
                self.assertEqual(diagnostic.status_code, 400)
                self.assertEqual(
                    diagnostic.get_json(),
                    {"error": "'External parser detail'", "error_language": "en-CA"},
                )
                self.assertEqual(self.database.read_bytes(), before)

    def test_html_pages_and_legacy_workbook_endpoints_are_absent(self):
        for path in (
            "/",
            "/setup",
            "/accounts",
            "/expenses",
            "/connections",
            "/transactions",
            "/settings",
            "/application-settings",
            "/about",
            "/disclaimer",
            "/salary-projection",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/api/sheets/Missing").status_code, 404)
        self.assertEqual(self.client.post("/api/import", json={}).status_code, 404)
        self.assertEqual(self.client.get("/api/taxes/years").status_code, 404)

    def test_financial_pages_localize_values_without_mutating_records(self):
        category = self.client.post(
            "/api/expenses/categories",
            json={"name": "Locale utilities", "classification": "required"},
        ).get_json()
        created = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Locale bill",
                "category_id": category["id"],
                "amount": "1234.50",
                "period_start": "2029-01-09",
                "period_end": "2029-02-09",
            },
        )
        self.assertEqual(created.status_code, 201)
        api_before = self.client.get("/api/expenses?year=2029").get_json()
        database_before = self.database.read_bytes()
        localization = self.app.extensions["localization"]
        for locale, amount, date, percent in (
            ("en-CA", "$1,234.50", "Jan 9, 2029", "25.69%"),
            ("fr-CA", "1\u00a0234,50\u00a0$", "9 janv. 2029", "25,69\u00a0%"),
        ):
            with self.subTest(locale=locale):
                localization.select(locale)
                expenses = self.client.get("/expenses?year=2029")
                self.assertEqual(expenses.status_code, 200)
                text = expenses.get_data(as_text=True)
                self.assertIn(amount, text)
                self.assertIn(date, text)
                self.assertNotIn("$1234.50", text)
                rules = self.client.get("/settings?jurisdiction=CA-QC&year=2026")
                self.assertEqual(rules.status_code, 200)
                self.assertIn(percent, rules.get_data(as_text=True))
                self.assertEqual(self.client.get("/api/expenses?year=2029").get_json(), api_before)
        self.assertEqual(self.database.read_bytes(), database_before)

    def test_factual_expense_workflow_validates_and_resolves_overlaps(self):
        category_response = self.client.post(
            "/api/expenses/categories",
            json={"name": "Overlap utilities", "classification": "required"},
        )
        self.assertEqual(category_response.status_code, 201)
        category_id = category_response.get_json()["id"]

        first = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Hydro",
                "category_id": category_id,
                "amount": "1200.00",
                "period_start": "2028-01-01",
                "period_end": "2028-12-31",
            },
        )
        second = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Hydro",
                "category_id": category_id,
                "amount": "1100.00",
                "period_start": "2028-01-01",
                "period_end": "2028-12-31",
            },
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        page = self.client.get("/expenses?year=2028")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Review required", self._visible_html(page))
        self.assertIn(b"Hydro", page.data)
        self.assertIn(b'id="expense-add"', page.data)
        self.assertIn(b'id="expense-categories"', page.data)
        self.assertIn(b'class="dashboard-panel expense-record-details" open', page.data)
        self.assertIn(b'id="expense-dialog-backdrop" class="dialog-backdrop" hidden', page.data)

        first_id = first.get_json()["id"]
        second_id = second.get_json()["id"]
        included = self.client.post(
            f"/api/expenses/{first_id}/overlap",
            json={"include": True, "note": "Use supported amount"},
        )
        excluded = self.client.post(
            f"/api/expenses/{second_id}/overlap",
            json={"include": False, "note": "Duplicate evidence"},
        )
        self.assertEqual(included.status_code, 200)
        self.assertEqual(excluded.status_code, 200)

        resolved_page = self.client.get("/expenses?year=2028")
        self.assertIn(b"$1,200.00", resolved_page.data)
        self.assertIn(b"Category totals", resolved_page.data)
        self.assertIn(b"Overlap utilities", resolved_page.data)
        self.assertIn(
            b"do not imply that every expense has been recorded",
            resolved_page.data,
        )
        self.assertNotIn(b"Review required", self._visible_html(resolved_page))
        self.assertIn(b'class="dashboard-panel expense-record-details">', resolved_page.data)

        invalid = self.client.post("/api/expenses/manual", json={})
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("error", invalid.get_json())

    def test_expense_form_workflow_redirects_back_to_the_application(self):
        response = self.client.post(
            "/expenses/categories",
            data={
                "csrf_token": "test-csrf-token",
                "year": "2026",
                "name": "Travel",
                "classification": "discretionary",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/expenses?", response.headers["Location"])
        self.assertIn("Expense+category+created", response.headers["Location"])
        self.assertIn("dialog=categories", response.headers["Location"])

        category_list = self.client.get(response.headers["Location"])
        self.assertIn(b'id="category-dialog-backdrop" class="dialog-backdrop">', category_list.data)
        self.assertIn(b"Expense category created.", category_list.data)
        self.assertIn(b"Travel", category_list.data)

    def test_expense_page_integrates_identity_overlap_and_period_estimation(self):
        utilities = self.client.post(
            "/api/expenses/categories",
            json={"name": "Integration utilities", "classification": "required"},
        ).get_json()
        property_tax = self.client.post(
            "/api/expenses/categories",
            json={"name": "Integration property tax", "classification": "required"},
        ).get_json()
        hydro = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Hydro",
                "category_id": utilities["id"],
                "amount": "31.00",
                "period_start": "2027-01-01",
                "period_end": "2027-01-31",
                "period_kind": "recurring_statement",
            },
        )
        energir = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Energir",
                "category_id": utilities["id"],
                "amount": "62.00",
                "period_start": "2027-01-01",
                "period_end": "2027-01-31",
                "period_kind": "recurring_statement",
            },
        )
        annual_tax = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Montreal property tax",
                "category_id": property_tax["id"],
                "amount": "4200.00",
                "period_start": "2027-06-01",
                "period_end": "2027-06-01",
                "period_kind": "annual_or_one_time",
            },
        )

        self.assertEqual(hydro.status_code, 201)
        self.assertEqual(energir.status_code, 201)
        self.assertEqual(annual_tax.status_code, 201)
        self.assertEqual(hydro.get_json()["overlap_status"], "clear")
        self.assertEqual(energir.get_json()["overlap_status"], "clear")
        page = self.client.get("/expenses?year=2027")
        self.assertNotIn(b"Review required", self._visible_html(page))
        self.assertIn(b'<label>View year<select id="expense-year-select"', page.data)
        self.assertIn(b'<option value="2027" selected>2027</option>', page.data)
        self.assertIn(b"Recorded total", page.data)
        self.assertIn(b"$4,293.00", page.data)
        self.assertIn(b'<header data-help-article="expenses">', page.data)
        self.assertIn(b"Seasonal estimate", page.data)
        self.assertIn(b"2.00% inflation", page.data)
        self.assertIn(b"Unavailable", page.data)
        self.assertIn(b'data-help-article="expense-seasonal-estimate"', page.data)
        self.assertIn(
            "preceding year's corresponding uncovered periods",
            unescape(page.get_data(as_text=True)),
        )
        estimate_help = next(
            article
            for article in self.client.get("/api/help").get_json()["articles"]
            if article["key"] == "expense-seasonal-estimate"
        )
        self.assertIn("E(y) = A(y,C) + (1 + i) \u00d7 P(U)", estimate_help["body"])
        self.assertIn("i = 2.00%", estimate_help["body"])
        self.assertIn("Annual and one-time expenses are never extrapolated", estimate_help["body"])
        expenses_help = next(
            article
            for article in self.client.get("/api/help").get_json()["articles"]
            if article["key"] == "expenses"
        )
        self.assertIn("required or discretionary categories", expenses_help["body"])
        self.assertIn("separate from projection assumptions", expenses_help["body"])

        import_result = self.client.get(
            "/expenses?year=2027&imported=3&imported_years=2025,2026,2027"
        )
        self.assertIn(b"3 expense statements saved", import_result.data)
        self.assertIn(b'href="/expenses?year=2025"', import_result.data)
        self.assertIn(b'href="/expenses?year=2026"', import_result.data)
        self.assertIn(b'href="/expenses?year=2027"', import_result.data)

        duplicate = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Hydro",
                "category_id": utilities["id"],
                "amount": "30.00",
                "period_start": "2027-01-01",
                "period_end": "2027-01-31",
                "period_kind": "recurring_statement",
            },
        )
        self.assertEqual(duplicate.status_code, 201)
        self.assertEqual(duplicate.get_json()["overlap_status"], "potential")
        records = self.client.get("/api/expenses?year=2027").get_json()
        hydro_statuses = [
            record["overlap_status"] for record in records if record["name"] == "Hydro"
        ]
        energir_statuses = [
            record["overlap_status"] for record in records if record["name"] == "Energir"
        ]
        self.assertEqual(hydro_statuses, ["potential", "potential"])
        self.assertEqual(energir_statuses, ["clear"])
        review_page = self.client.get("/expenses?year=2027")
        self.assertIn(b"Review required", self._visible_html(review_page))

        included = self.client.post(
            f"/api/expenses/{hydro.get_json()['id']}/overlap",
            json={"include": True, "note": "Confirmed statement"},
        )
        excluded = self.client.post(
            f"/api/expenses/{duplicate.get_json()['id']}/overlap",
            json={"include": False, "note": "Duplicate statement"},
        )
        self.assertEqual(included.status_code, 200)
        self.assertEqual(excluded.status_code, 200)

        resolved = self.client.get("/expenses?year=2027")
        self.assertNotIn(b"Review required", self._visible_html(resolved))
        self.assertIn(b"$4,293.00", resolved.data)
        self.assertIn(b"Unavailable", resolved.data)

    def test_expense_page_supports_recurring_evidence_in_year_9999(self):
        category = self.client.post(
            "/api/expenses/categories",
            json={"name": "Far-future utilities", "classification": "required"},
        )
        self.assertEqual(category.status_code, 201)
        expense = self.client.post(
            "/api/expenses/manual",
            json={
                "name": "Hydro",
                "category_id": category.get_json()["id"],
                "amount": "31.00",
                "period_start": "9999-01-01",
                "period_end": "9999-01-31",
                "period_kind": "recurring_statement",
            },
        )
        self.assertEqual(expense.status_code, 201)

        page = self.client.get("/expenses?year=9999")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b"9999 spending", page.data)
        self.assertIn(b"$31.00", page.data)
        self.assertIn(b"Seasonal estimate", page.data)
        self.assertIn(b"Unavailable", page.data)

    def test_pages_load_native_javascript_modules(self):
        expected_entries = {
            "/": "dashboard/dashboard.mjs",
            "/setup": "setup/setup.mjs",
            "/accounts": "accounts/accounts.mjs",
            "/income": "income/income.mjs",
            "/expenses": "expenses/expenses.mjs",
            "/connections": "connections/connections.mjs",
            "/transactions": "transactions/transactions.mjs",
            "/salary-projection": "projections/salary-projection.mjs",
        }
        for path, filename in expected_entries.items():
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertIn(b'type="module"', page.data)
                self.assertRegex(
                    page.data,
                    rb'src="/static/' + re.escape(filename.encode()) + rb'(?:\?[^" ]*)?"',
                )
        for filename in (
            "connections/button-action.mjs",
            "connections/connections.mjs",
            "dashboard/dashboard.mjs",
            "shared/html.mjs",
            "transactions/latest-request.mjs",
            "setup/setup-values.mjs",
            "setup/setup.mjs",
            "transactions/transactions-render.mjs",
            "transactions/transaction-import-message.mjs",
            "transactions/transactions.mjs",
            "accounts/accounts.mjs",
            "accounts/account-dialog.mjs",
            "accounts/accounts-api.mjs",
            "accounts/accounts-format.mjs",
            "accounts/accounts-real-estate.mjs",
            "accounts/accounts-render.mjs",
            "accounts/accounts-state.mjs",
            "shared/form-state.mjs",
            "accounts/gic-dialog.mjs",
            "accounts/ownership-fields.mjs",
            "projections/salary-projection.mjs",
            "income/income.mjs",
            "income/income-corrections.mjs",
            "expenses/expenses.mjs",
            "help/help.mjs",
        ):
            with self.subTest(filename=filename):
                response = self.client.get(f"/static/{filename}")
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("javascript", response.content_type)
                finally:
                    response.close()

    def test_shared_browser_modules_use_only_canonical_nested_urls(self):
        for module in (
            "account-types",
            "form-state",
            "html",
            "i18n",
            "income-source-label",
            "locale-format",
        ):
            with self.subTest(module=module):
                response = self.client.get(f"/static/shared/{module}.mjs")
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("javascript", response.content_type)
                finally:
                    response.close()
                old_response = self.client.get(f"/static/{module}.mjs")
                try:
                    self.assertEqual(old_response.status_code, 404)
                finally:
                    old_response.close()

    def test_feature_browser_modules_use_only_canonical_nested_urls(self):
        modules = {
            "accounts": (
                "account-dialog",
                "accounts-api",
                "accounts-format",
                "accounts-real-estate",
                "accounts-render",
                "accounts-state",
                "accounts",
                "gic-dialog",
                "ownership-fields",
            ),
            "dashboard": ("dashboard",),
            "setup": ("setup-values", "setup"),
            "income": ("income", "income-corrections"),
            "expenses": ("expenses",),
            "projections": ("salary-projection",),
            "help": ("help",),
            "connections": ("button-action", "connections"),
            "transactions": (
                "latest-request",
                "transaction-import-message",
                "transactions-render",
                "transactions",
            ),
        }
        for feature, names in modules.items():
            for name in names:
                with self.subTest(module=name):
                    response = self.client.get(f"/static/{feature}/{name}.mjs")
                    try:
                        self.assertEqual(response.status_code, 200)
                        self.assertIn("javascript", response.content_type)
                    finally:
                        response.close()
                    old_response = self.client.get(f"/static/{name}.mjs")
                    try:
                        self.assertEqual(old_response.status_code, 404)
                    finally:
                        old_response.close()

    def test_primary_pages_share_one_canonical_help_module_url(self):
        module_urls = set()
        for path in (
            "/",
            "/setup",
            "/accounts",
            "/transactions",
            "/connections",
            "/income",
            "/expenses",
            "/salary-projection",
        ):
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertEqual(page.status_code, 200)
                help_urls = re.findall(rb'src="([^"]*help\.mjs(?:\?[^"]*)?)"', page.data)
                self.assertTrue(help_urls)
                self.assertEqual(len(set(help_urls)), 1)
                self.assertEqual(help_urls[0].partition(b"?")[0], b"/static/help/help.mjs")
                module_urls.update(help_urls)
        self.assertEqual(len(module_urls), 1)

    def test_browser_modules_are_nested_and_classic_assets_keep_root_urls(self):
        static_root = Path(__file__).parents[1] / "static"
        self.assertEqual(list(static_root.glob("*.mjs")), [])
        for name, content_type in (("csrf.js", "javascript"), ("style.css", "text/css")):
            with self.subTest(asset=name):
                response = self.client.get(f"/static/{name}")
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(content_type, response.content_type)
                finally:
                    response.close()

    def test_setup_exposes_browser_localization_before_its_module(self):
        self.app.extensions["localization"].select("fr-CA")
        page = self.client.get("/setup")

        self.assertEqual(page.status_code, 200)
        localization_position = page.data.index(b'id="browser-localization"')
        module_position = page.data.index(b"setup.mjs")
        self.assertLess(localization_position, module_position)
        self.assertIn(b'"locale": "fr-CA"', page.data)
        self.assertIn(b'"birth_date": "Date de naissance"', page.data)

    def test_salary_projection_api_persists_inputs_and_calculates_household(self):
        person_id = self._people()[0]["id"]
        scenario = self.client.post(
            "/api/model/scenarios",
            json={"name": "Salary baseline", "baseline_date": "2026-01-01"},
        )
        self.assertEqual(scenario.status_code, 201)
        scenario_id = scenario.get_json()["id"]
        baseline = self.client.put(
            f"/api/salary-projection/people/{person_id}/baseline",
            json={
                "effective_date": "2026-01-01",
                "annual_salary": "100000",
                "province_of_employment": "ON",
                "payroll_plan": "CPP",
            },
        )
        self.assertEqual(baseline.status_code, 200)
        settings = self.client.put(
            f"/api/salary-projection/scenarios/{scenario_id}/people/{person_id}/settings",
            json={
                "default_raise": "0.04",
                "recurring_rrsp_contribution": "10000",
                "recurring_rrsp_deduction": "10000",
                "recurring_other_income": "1000",
            },
        )
        self.assertEqual(settings.status_code, 200)
        partial_settings = self.client.put(
            f"/api/salary-projection/scenarios/{scenario_id}/people/{person_id}/settings",
            json={"default_raise": "0.04"},
        )
        self.assertEqual(partial_settings.status_code, 200)
        self.assertEqual(partial_settings.get_json()["recurring_rrsp_contribution"], "10000.00")
        self.assertEqual(partial_settings.get_json()["recurring_other_income"], "1000.00")
        with self.runtime_config.connect() as connection:
            approvals = PublicRuleApprovalRepository(connection)
            catalog = PublicRuleCatalog(application.ROOT / "public_rules")
            for rule_set_id in (
                "ca-2026-official",
                "ca-qc-2026-official",
                "ca-on-2026-official",
            ):
                package = catalog.get(rule_set_id)
                self.assertIsNotNone(package)
                approvals.approve(rule_set_id, package.content_hash)

        expenses = self.client.put(
            f"/api/salary-projection/scenarios/{scenario_id}/expenses",
            json={
                "start_year": 2026,
                "required_annual_amount": "60000",
                "required_annual_growth": "0.02",
                "discretionary_annual_amount": "10000",
                "discretionary_annual_growth": "0.03",
            },
        )
        self.assertEqual(expenses.status_code, 200)
        self.assertEqual(expenses.get_json()["required_annual_amount"], "60000.00")

        response = self.client.get(
            f"/api/salary-projection?scenario_id={scenario_id}&start_year=2026&end_year=2027"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        person = next(item for item in payload["people"] if item["id"] == person_id)
        self.assertEqual(person["projection"][0]["annual_salary_rate"], "105560.00")
        self.assertEqual(person["projection"][1]["annual_salary_rate"], "109782.40")
        self.assertTrue(person["projection"][1]["rules_held_constant"])
        self.assertEqual(len(payload["household"]), 2)
        household = payload["household"][0]
        self.assertEqual(household["required_expenses"], "60000.00")
        self.assertEqual(household["discretionary_expenses"], "10000.00")
        self.assertEqual(household["planned_expenses"], "70000.00")
        self.assertEqual(
            Decimal(household["surplus_deficit"]),
            Decimal(household["disposable_income"]) - Decimal("70000.00"),
        )

        rejected = self.client.put(
            f"/api/salary-projection/scenarios/{scenario_id}/people/{person_id}/overrides",
            json={"overrides": [{"year": 2026, "salary": "130000"}, {"salary": "1"}]},
        )
        self.assertEqual(rejected.status_code, 400)
        unchanged = self.client.get(
            f"/api/salary-projection?scenario_id={scenario_id}&start_year=2026&end_year=2026"
        ).get_json()
        unchanged_person = next(item for item in unchanged["people"] if item["id"] == person_id)
        self.assertEqual(unchanged_person["projection"][0]["annual_salary_rate"], "105560.00")

        override = self.client.put(
            f"/api/salary-projection/scenarios/{scenario_id}/people/{person_id}/overrides",
            json={"overrides": [{"year": 2027, "salary": "120000", "rrsp_contribution": "0"}]},
        )
        self.assertEqual(override.status_code, 200)
        self.assertEqual(override.get_json()["saved_years"], [2027])
        actual = self.client.put(
            f"/api/salary-projection/people/{person_id}/actuals/2025",
            json={
                "salary_income": "95000",
                "province_of_residence": "ON",
                "payroll_plan": "CPP",
                "rrsp_contribution": "9000",
                "rrsp_deduction": "9000",
                "cpp_qpp": "4000",
                "ei": "1000",
                "federal_tax": "12000",
                "quebec_tax": "14000",
            },
        )
        self.assertEqual(actual.status_code, 200)
        earlier_actual = self.client.put(
            f"/api/salary-projection/people/{person_id}/actuals/2024",
            json={
                "salary_income": "90000",
                "province_of_residence": "ON",
                "cpp_qpp": "3800",
                "ei": "900",
                "federal_tax": "11000",
                "quebec_tax": "13000",
            },
        )
        self.assertEqual(earlier_actual.status_code, 200)

        updated = self.client.get(
            f"/api/salary-projection?scenario_id={scenario_id}&start_year=2026&end_year=2027"
        ).get_json()
        person = next(item for item in updated["people"] if item["id"] == person_id)
        self.assertEqual(person["projection"][0]["annual_salary_rate"], "98800.00")
        self.assertEqual(person["projection"][1]["annual_salary_rate"], "120000.00")
        self.assertEqual(person["projection"][1]["rrsp_contribution"], "0.00")
        self.assertEqual([item["year"] for item in person["actuals"]], [2024, 2025])
        self.assertEqual(person["actuals"][0]["age"], 49)
        self.assertEqual(person["actuals"][0]["net_income_after_tax"], "61300.00")
        self.assertEqual(person["salary_anchor"]["annual_salary_rate"], "95000.00")

        reset = self.client.put(
            f"/api/salary-projection/scenarios/{scenario_id}/people/{person_id}/draft",
            json={
                "settings": {"default_raise": "0.04", "retirement_date": None},
                "overrides": [
                    {
                        "year": 2027,
                        "salary": None,
                        "raise_rate": None,
                        "rrsp_contribution": None,
                        "rrsp_deduction": None,
                        "other_income": None,
                    }
                ],
            },
        )
        self.assertEqual(reset.status_code, 200)
        reset_projection = self.client.get(
            f"/api/salary-projection?scenario_id={scenario_id}&start_year=2026&end_year=2027"
        ).get_json()
        reset_person = next(item for item in reset_projection["people"] if item["id"] == person_id)
        self.assertEqual(reset_person["overrides"], [])
        self.assertEqual(reset_person["projection"][1]["annual_salary_rate"], "102752.00")

    def test_salary_projection_save_as_clones_every_person_and_applies_visible_draft(self):
        people = self._people()
        source = self.client.post(
            "/api/model/scenarios",
            json={
                "name": "Source projection",
                "baseline_date": "2026-01-01",
                "growth_rate": "0.025",
            },
        )
        self.assertEqual(source.status_code, 201)
        source_id = source.get_json()["id"]
        with self.runtime_config.connect() as connection:
            asset_id = RealEstateAssetRepository(connection).list_all()[0].id
            RealEstateProjectionRepository(connection).create(
                asset_id,
                "2035-01-01",
                "250000",
                scenario_id=source_id,
                projected_acb="125000",
                note="Scenario-specific land value",
            )
        for index, person in enumerate(people[:2]):
            person_id = person["id"]
            settings = self.client.put(
                f"/api/salary-projection/scenarios/{source_id}/people/{person_id}/settings",
                json={"default_raise": str(Decimal("0.03") + Decimal(index) / 100)},
            )
            self.assertEqual(settings.status_code, 200)
            override = self.client.put(
                f"/api/salary-projection/scenarios/{source_id}/people/{person_id}/overrides",
                json={"overrides": [{"year": 2027, "salary": str(100000 + index * 10000)}]},
            )
            self.assertEqual(override.status_code, 200)

        selected_person_id = people[0]["id"]
        clone = self.client.post(
            f"/api/salary-projection/scenarios/{source_id}/clone",
            json={
                "name": "Alternative projection",
                "person_id": selected_person_id,
                "settings": {"default_raise": "0.05", "retirement_date": "2035-07-01"},
                "overrides": [{"year": 2027, "salary": "125000"}],
            },
        )
        self.assertEqual(clone.status_code, 201)
        clone_id = clone.get_json()["id"]

        cloned = self.client.get(
            f"/api/salary-projection?scenario_id={clone_id}&start_year=2026&end_year=2027"
        ).get_json()
        cloned_people = {item["id"]: item for item in cloned["people"]}
        self.assertEqual(cloned_people[selected_person_id]["settings"]["default_raise"], "0.05")
        self.assertEqual(
            cloned_people[selected_person_id]["settings"]["retirement_date"], "2035-07-01"
        )
        self.assertEqual(cloned_people[selected_person_id]["overrides"][0]["salary"], "125000.00")
        second_person_id = people[1]["id"]
        self.assertEqual(cloned_people[second_person_id]["settings"]["default_raise"], "0.04")
        self.assertEqual(cloned_people[second_person_id]["overrides"][0]["salary"], "110000.00")

        original = self.client.get(
            f"/api/salary-projection?scenario_id={source_id}&start_year=2026&end_year=2027"
        ).get_json()
        original_people = {item["id"]: item for item in original["people"]}
        self.assertEqual(original_people[selected_person_id]["settings"]["default_raise"], "0.03")
        self.assertEqual(original_people[selected_person_id]["overrides"][0]["salary"], "100000.00")
        with self.runtime_config.connect() as connection:
            assumption = ScenarioAssumptionRepository(connection).get(
                clone_id, "general_growth_rate"
            )
            real_estate = RealEstateProjectionRepository(connection).list_for_scenario(clone_id)
        self.assertIsNotNone(assumption)
        self.assertEqual(assumption.value, "0.025")
        self.assertEqual(len(real_estate), 1)
        self.assertEqual(real_estate[0].projected_value, 250000.0)

        rejected = self.client.post(
            f"/api/salary-projection/scenarios/{source_id}/clone",
            json={"name": "Incomplete projection", "person_id": selected_person_id},
        )
        self.assertEqual(rejected.status_code, 400)
        scenarios = self.client.get("/api/salary-projection").get_json()["scenarios"]
        self.assertNotIn("Incomplete projection", [item["name"] for item in scenarios])

    def test_ufile_preview_does_not_save_until_user_confirms(self):
        person_id = self._people()[0]["id"]
        parsed = ParsedUFileTaxReturn(
            tax_year=2024,
            employment_income=Decimal("100000.00"),
            other_employment_income=Decimal("500.00"),
            cpp_qpp=Decimal("4000.00"),
            ei=Decimal("900.00"),
            qpip=Decimal("400.00"),
            rrsp_contribution=Decimal("15000.00"),
            rrsp_deduction=Decimal("14000.00"),
            federal_tax=Decimal("12000.00"),
            provincial_tax=Decimal("13000.00"),
            taxpayer_name="Alex Example",
            tax_values=(
                ParsedTaxValue(
                    "interest_investment_income",
                    "Interest and other investment income",
                    Decimal("725.50"),
                    line_code="12100",
                    effective_year=2024,
                ),
            ),
        )
        with patch("web.income_routes.income_source_registry.detect") as detect_source:
            detect_source.return_value.parser.return_value = parsed
            detect_source.return_value.source_label = "UFile T1"
            detect_source.return_value.key = "ufile"
            detect_source.return_value.display_name = "UFile T1 PDF"
            detect_source.return_value.version = "2026.09.29"
            detect_source.return_value.help_text = "Help"
            response = self.client.post(
                "/api/income/import/ufile/preview",
                data={"file": (io.BytesIO(b"synthetic"), "return.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["employment_income"], "100000.00")
        self.assertEqual(response.get_json()["taxpayer_name"], "Alex Example")
        self.assertEqual(response.get_json()["interest_income"], "725.50")
        record = self.client.get(f"/api/income?person_id={person_id}&year=2024").get_json()
        self.assertIsNone(record["record"])

    def test_notice_preview_and_confirmation_save_assessment_and_rrsp_room(self):
        person_id = self._people()[0]["id"]
        parsed = ParsedTaxAssessment(
            tax_year=2025,
            jurisdiction="CA",
            issued_on="2026-05-11",
            taxpayer_name="Alex Example",
            total_income=Decimal("105000.00"),
            net_income=Decimal("90000.00"),
            taxable_income=Decimal("89500.00"),
            net_tax=Decimal("17500.00"),
            additional_contributions=Decimal("0.00"),
            tax_withheld=Decimal("18000.00"),
            balance=Decimal("-500.00"),
            rrsp_effective_year=2026,
            rrsp_deduction_limit=Decimal("22000.00"),
            rrsp_unused_deduction_room=Decimal("3000.00"),
            rrsp_new_room=Decimal("19000.00"),
            rrsp_unused_contributions=Decimal("1200.00"),
            rrsp_available_room=Decimal("20800.00"),
            tax_values=(
                ParsedTaxValue(
                    "canada_training_credit_limit",
                    "Canada training credit limit",
                    None,
                    Decimal("250"),
                    effective_year=2026,
                ),
            ),
        )
        with patch("web.income_routes.tax_notice_registry.detect") as detect_notice:
            detect_notice.return_value.parser.return_value = parsed
            detect_notice.return_value.source_label = "CRA notice of assessment"
            detect_notice.return_value.display_name = "CRA notice of assessment PDF"
            detect_notice.return_value.version = "2026.09.29"
            preview = self.client.post(
                "/api/income/import/preview",
                data={"file": (io.BytesIO(b"notice"), "notice.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(preview.status_code, 200)
        payload = preview.get_json()
        self.assertEqual(payload["kind"], "tax_assessment")
        self.assertEqual(payload["rrsp_available_room"], "20800.00")
        self.assertEqual(len(payload["document_hash"]), 64)
        saved = self.client.post(
            f"/api/income/people/{person_id}/assessments",
            json=payload,
        )
        self.assertEqual(saved.status_code, 201)

        income = self.client.get(f"/api/income?person_id={person_id}").get_json()
        self.assertEqual(income["assessments"][0]["net_tax"], "17500.00")
        self.assertEqual(income["registered_rooms"][0]["effective_year"], 2026)
        self.assertEqual(income["registered_rooms"][0]["available_room"], "20800.00")
        self.assertEqual(income["tax_values"][0]["concept"], "canada_training_credit_limit")
        self.assertEqual(income["snapshot"]["tax_year"], 2025)
        snapshot_values = {value["concept"]: value for value in income["snapshot"]["values"]}
        self.assertEqual(snapshot_values["total_income"]["amount"], "105000.00")
        self.assertEqual(snapshot_values["total_income"]["source"], "CRA notice of assessment")

    def test_pension_preview_and_confirmation_save_earnings_and_estimates(self):
        person_id = self._people()[0]["id"]
        parsed = ParsedPublicPensionStatement(
            issued_on="2026-06-15",
            taxpayer_name="Alex Example",
            birth_date="1975-01-02",
            provider="QPP",
            excludes_second_enhancement=True,
            earnings=((2024, Decimal("0"), Decimal("68500"), "C"),),
            estimates=(
                ("continue", 60, Decimal("900")),
                ("continue", 65, Decimal("1400")),
                ("stop", 60, Decimal("700")),
                ("stop", 65, Decimal("1100")),
            ),
        )
        with (
            patch("web.income_routes.tax_notice_registry.detect", return_value=None),
            patch("web.income_routes.public_pension_source_registry.detect") as detect_pension,
        ):
            detect_pension.return_value.parser.return_value = parsed
            detect_pension.return_value.display_name = "Retraite Québec statement"
            detect_pension.return_value.version = "2026.09.29"
            preview = self.client.post(
                "/api/income/import/preview",
                data={"file": (io.BytesIO(b"statement"), "statement.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(preview.status_code, 200)
        payload = preview.get_json()
        self.assertEqual(payload["kind"], "public_pension_statement")
        self.assertEqual(payload["earnings"][0]["cpp_earnings"], "68500.00")
        saved = self.client.post(
            f"/api/income/people/{person_id}/public-pension-statements",
            json=payload,
        )
        self.assertEqual(saved.status_code, 201)

        pension = self.client.get(f"/api/income?person_id={person_id}").get_json()["public_pension"]
        self.assertEqual(pension["provider"], "QPP")
        self.assertTrue(pension["excludes_second_enhancement"])
        self.assertEqual(pension["earnings"][0]["cpp_earnings"], "68500.00")
        self.assertEqual(len(pension["estimates"]), 4)

    def test_income_history_keeps_all_years_newest_first(self):
        person_id = self._people()[0]["id"]
        response = self.client.put(
            f"/api/income/people/{person_id}/years/2024",
            json={
                "employment_income": "90000",
                "bonus": "5000",
                "province_of_residence": "ON",
                "source": "T1",
                "interest_income": "425.75",
            },
        )
        self.assertEqual(response.status_code, 200)

        history = self.client.get(f"/api/income?person_id={person_id}")

        self.assertEqual(history.status_code, 200)
        records = history.get_json()["records"]
        self.assertGreaterEqual(len(records), 2)
        self.assertEqual([record["year"] for record in records[:2]], [2025, 2024])
        self.assertEqual(records[1]["salary_rate"], "85000.00")
        self.assertEqual(records[1]["province_of_residence"], "ON")
        self.assertEqual(records[1]["interest_income"], "425.75")

    def test_income_snapshot_api_returns_correctly_structured_data(self):
        person_id = self._people()[0]["id"]
        # Setup: 1 annual record, 1 assessment
        self.client.put(
            f"/api/income/people/{person_id}/years/2025",
            json={
                "employment_income": "100000",
                "bonus": "5000",
                "province_of_residence": "ON",
                "source": "T1",
            },
        )

        assessment_payload = {
            "tax_year": 2025,
            "jurisdiction": "CA",
            "issued_on": "2026-05-11",
            "taxpayer_name": "Alex Example",
            "total_income": "120000.00",
            "net_income": "100000.00",
            "taxable_income": "95000.00",
            "net_tax": "20000.00",
            "additional_contributions": "0.00",
            "tax_withheld": "22000.00",
            "balance": "-2000.00",
            "rrsp_effective_year": 2026,
            "rrsp_deduction_limit": "25000.00",
            "rrsp_unused_deduction_room": "5000.00",
            "rrsp_new_room": "20000.00",
            "rrsp_unused_contributions": "0.00",
            "rrsp_available_room": "25000.00",
            "source": "CRA Assessment",
            "source_version": "1.0",
            "document_hash": "a" * 64,
        }
        self.client.post(
            f"/api/income/people/{person_id}/assessments",
            json=assessment_payload,
        )

        response = self.client.get(f"/api/income?person_id={person_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("snapshot", data)
        self.assertIn("records", data)
        self.assertIn("assessments", data)
        self.assertIn("registered_rooms", data)
        self.assertIn("public_pension", data)
        self.assertIn("tax_values", data)

        snapshot = data["snapshot"]
        self.assertEqual(snapshot["tax_year"], 2025)
        self.assertIsInstance(snapshot["values"], list)

        # Verify snapshot values include required concepts
        concepts = {v["concept"] for v in snapshot["values"]}
        self.assertIn("employment_income", concepts)
        self.assertIn("total_income", concepts)
        self.assertIn("taxable_income", concepts)

    def test_income_snapshot_precedence_via_api(self):
        person_id = self._people()[0]["id"]
        # 1. Manual Record (lowest precedence)
        self.client.put(
            f"/api/income/people/{person_id}/years/2025",
            json={
                "employment_income": "100000",
                "bonus": "0",
                "province_of_residence": "ON",
                "source": "Manual",
            },
        )

        response = self.client.get(f"/api/income?person_id={person_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Check that the snapshot reflects the manual record for now
        snapshot_values = {v["concept"]: v for v in data["snapshot"]["values"]}
        self.assertEqual(snapshot_values["employment_income"]["amount"], "100000.00")
        self.assertEqual(snapshot_values["employment_income"]["source"], "Manual")

    def test_state_changes_require_a_matching_csrf_token(self):
        untrusted_client = self.app.test_client()
        page = untrusted_client.get("/accounts")
        self.assertIn(b'<meta name="csrf-token"', page.data)
        self.assertEqual(untrusted_client.post("/api/model/people", json={}).status_code, 403)
        self.assertEqual(
            untrusted_client.post(
                "/api/model/people", json={}, headers={"X-CSRF-Token": "wrong"}
            ).status_code,
            403,
        )
        self.assertEqual(self.client.post("/api/model/people", json={}).status_code, 400)

    def test_public_rule_approval_is_bound_to_server_verified_hash(self):
        package = PublicRuleCatalog(application.ROOT / "public_rules").get("ca-2026-official")
        self.assertIsNotNone(package)

        mismatch = self.client.post(
            "/public-rules/ca-2026-official/approve",
            data={"content_hash": "0" * 64},
        )
        self.assertEqual(mismatch.status_code, 409)

        approved = self.client.post(
            "/public-rules/ca-2026-official/approve",
            data={"content_hash": package.content_hash},
        )
        self.assertEqual(approved.status_code, 302)
        self.assertIn("jurisdiction=CA&year=2026", approved.headers["Location"])
        with self.runtime_config.connect() as connection:
            row = connection.execute(
                """
                SELECT content_hash FROM public_rule_approvals
                WHERE rule_set_id = 'ca-2026-official'
                """
            ).fetchone()
        self.assertEqual(row[0], package.content_hash)
        page = self.client.get("/settings")
        self.assertIn(b"Approved", page.data)
        self.assertEqual(
            self.client.post(
                "/public-rules/missing/approve", data={"content_hash": "0" * 64}
            ).status_code,
            404,
        )

    def test_public_rules_are_filtered_by_jurisdiction_and_year(self):
        default_page = self.client.get("/settings")
        self.assertIn(b">Federal</a>", default_page.data)
        self.assertIn(b">Alberta</a>", default_page.data)
        self.assertIn(b">Quebec</a>", default_page.data)
        self.assertIn(b">Ontario</a>", default_page.data)
        self.assertIn(b">Yukon</a>", default_page.data)
        self.assertIn(b'<option value="2026" selected>2026</option>', default_page.data)
        self.assertIn(b'<option value="2025">2025</option>', default_page.data)
        self.assertIn(b"ca-2026-official", default_page.data)
        self.assertNotIn(b"ca-qc-2026-official", default_page.data)
        self.assertIn(b'data-help-article="public-rule-approval"', default_page.data)

        help_response = self.client.get("/api/help")
        self.assertEqual(help_response.status_code, 200)
        self.assertEqual(help_response.get_json()["language"], "en-CA")
        approval_help = next(
            article
            for article in help_response.get_json()["articles"]
            if article["key"] == "public-rule-approval"
        )
        self.assertIn("added, removed, or changed tax concepts", approval_help["body"])
        self.assertIn("importer code change", approval_help["body"])

        quebec_2025 = self.client.get("/settings?jurisdiction=CA-QC&year=2025")
        self.assertIn(b"ca-qc-2025-official", quebec_2025.data)
        self.assertNotIn(b"ca-qc-2026-official", quebec_2025.data)
        self.assertIn(b'<option value="2025" selected>2025</option>', quebec_2025.data)

    def test_public_rules_show_effective_combined_rates_for_supported_province(self):
        response = self.client.get("/settings?jurisdiction=CA-QC&year=2026")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Effective combined marginal tax", response.data)
        self.assertIn(b"25.69%", response.data)
        self.assertIn(b"53.31%", response.data)

        alberta = self.client.get("/settings?jurisdiction=CA-AB&year=2026")
        self.assertIn(b"Effective combined marginal tax", alberta.data)
        self.assertIn(b"22.00%", alberta.data)
        self.assertIn(b"48.00%", alberta.data)

    def test_institution_discovery_exposes_import_connection_and_help_capabilities(self):
        response = self.client.get("/api/institutions")
        self.assertEqual(response.status_code, 200)
        providers = {item["key"]: item for item in response.get_json()["institutions"]}

        self.assertEqual(len(providers["rbc"]["importers"]), 4)
        self.assertIsNone(providers["rbc"]["connection"])
        self.assertEqual(
            providers["questrade"]["connection"]["sync_path"], "/api/connections/questrade/sync"
        )
        self.assertEqual(providers["questrade"]["version"], "2026.09.29")
        self.assertIn(
            "connection", {topic["key"] for topic in providers["questrade"]["help_topics"]}
        )

    def test_income_source_contract_exposes_retrieval_help_and_calver(self):
        page = self.client.get("/income")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'data-help-article="income-source-ufile"', page.data)

        sources = self.client.get("/api/income/sources")
        self.assertEqual(sources.status_code, 200)
        source = sources.get_json()["sources"][0]
        self.assertEqual(source["key"], "ufile")
        self.assertEqual(source["version"], "2026.09.29.1")
        self.assertNotIn("last_changed", source)
        self.assertIn("Tax Return - view or download", source["help_text"])

        help_catalog = self.client.get("/api/help").get_json()
        ufile_help = next(
            article
            for article in help_catalog["articles"]
            if article["key"] == "income-source-ufile"
        )
        self.assertIn("Tax Return - view or download", ufile_help["body"])

        about = self.client.get("/about")
        self.assertIn(b"Income source modules", about.data)
        self.assertIn(b"Institution modules", about.data)
        self.assertIn(b"UFile T1 PDF", about.data)

    def test_help_hierarchy_and_provider_metadata(self):
        catalog = self.client.get("/api/help").get_json()
        categories = {item["key"]: item for item in catalog["categories"]}
        for key in ("summary", "assets", "income", "expenses", "transactions"):
            self.assertEqual(categories[key]["parent"], "financial")
        articles = {item["key"]: item for item in catalog["articles"]}
        self.assertEqual(articles["summary"]["category"], "summary")
        self.assertEqual(articles["summary"]["owning_page"], "/")
        self.assertEqual(articles["connections"]["category"], "connections")
        self.assertEqual(articles["institution-rbc-imports"]["category"], "imports")
        self.assertEqual(articles["institution-questrade-connection"]["category"], "connections")
        self.assertEqual(articles["income-source-ufile"]["category"], "tax-documents")
        self.assertEqual(articles["expense-source-hydro-quebec"]["category"], "expense-imports")
        provider = SimpleNamespace(
            key="synthetic",
            display_name="Synthetic",
            help_topics=(
                HelpTopic(
                    "guide",
                    "Guide",
                    "Text",
                    category="expenses",
                    parent_topic="expenses",
                    order=7,
                    owning_page="/expenses",
                ),
                HelpTopic("unknown", "Unknown", "Text", category="unsupported"),
            ),
        )
        with patch(
            "web.help_routes.institution_registry",
            return_value=SimpleNamespace(providers=(provider,)),
        ):
            contributed = {
                item["key"]: item for item in self.client.get("/api/help").get_json()["articles"]
            }
        guide = contributed["institution-synthetic-guide"]
        self.assertEqual(
            (guide["category"], guide["parent_topic"], guide["order"], guide["owning_page"]),
            ("expenses", "expenses", 7, "/expenses"),
        )
        self.assertEqual(contributed["institution-synthetic-unknown"]["category"], "application")

    def test_financial_disclaimer_is_accessible_from_projection_and_about(self):
        projection = self.client.get("/salary-projection")
        self.assertIn(b"Projections are estimates for planning purposes only", projection.data)
        self.assertIn(b"not financial, tax, investment", projection.data)
        self.assertIn(b'href="/disclaimer"', projection.data)

        about = self.client.get("/about")
        self.assertIn(b"Copyright 2026 Mindstep Corporation", about.data)
        self.assertIn(b"PolyForm Noncommercial 1.0.0", about.data)
        self.assertIn(b'href="mailto:info@mindstep.ca"', about.data)
        self.assertIn(b'href="/disclaimer"', about.data)

        disclaimer = self.client.get("/disclaimer")
        self.assertEqual(disclaimer.status_code, 200)
        self.assertIn(b"informational, planning, and modelling purposes only", disclaimer.data)
        self.assertIn(b"without warranty of any kind", disclaimer.data)

    def test_general_pages_describe_a_broad_financial_application(self):
        summary = self.client.get("/")
        self.assertIn(b"ForeView | Financial summary", summary.data)
        self.assertIn(b"ForeView", summary.data)
        self.assertNotIn(b"Retirement model", summary.data)

        setup = self.client.get("/setup")
        self.assertIn(b"financial records and projections", setup.data)

        about = self.client.get("/about")
        self.assertIn(b"Understand, manage, and model your financial life", about.data)
        self.assertIn(b"personal and household financial management", about.data)

    def test_disclaimer_page_reads_the_authoritative_markdown_file(self):
        disclaimer_path = self.runtime / "test-disclaimer.md"
        disclaimer_path.write_text(
            "# Test disclaimer\n\nCanonical runtime disclaimer content.\n", encoding="utf-8"
        )
        with patch("web.page_routes.DISCLAIMER_PATH", disclaimer_path):
            response = self.client.get("/disclaimer")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test disclaimer", response.data)
        self.assertIn(b"Canonical runtime disclaimer content.", response.data)

    def test_people_can_be_created_and_updated(self):
        created = self.client.post(
            "/api/model/people", json={"name": "Casey Example", "birth_date": "1980-04-03"}
        )
        self.assertEqual(created.status_code, 201)
        person_id = created.get_json()["id"]
        updated = self.client.put(
            f"/api/model/people/{person_id}", json={"birth_date": "1981-05-04"}
        )
        self.assertEqual(updated.status_code, 200)
        person = next(item for item in self._people() if item["id"] == person_id)
        self.assertEqual(person["birth_date"], "1981-05-04")
        self.assertEqual(self.client.post("/api/model/people", json={}).status_code, 400)

    def test_account_balance_and_gic_routes_persist_values(self):
        owner_id = self._people()[0]["id"]
        created = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Route savings",
                "category": "non_registered",
                "account_number": "ROUTE-001",
                "institution": "Synthetic Bank",
                "owners": [{"person_id": owner_id, "share": 1}],
                "interest_rate": "3.5",
                "balance_amount": "1000",
                "balance_date": "2026-01-01",
            },
        )
        self.assertEqual(created.status_code, 201)
        account_id = created.get_json()["id"]
        balance = self.client.post(
            f"/api/model/accounts/{account_id}/balance",
            json={"date": "2026-02-01", "amount": 1100, "interest_rate": 3.75},
        )
        self.assertEqual(balance.status_code, 201)
        gic = self.client.post(
            f"/api/model/accounts/{account_id}/gics",
            json={
                "name": "Route GIC",
                "principal": 500,
                "interest_rate": 0.04,
                "start_date": "2026-02-01",
                "maturity_date": "2027-02-01",
                "redeemable": True,
            },
        )
        self.assertEqual(gic.status_code, 201)
        account_data = self.client.get("/api/model/accounts").get_json()["accounts"]
        account = next(item for item in account_data if item["id"] == account_id)
        self.assertEqual(account["latest_amount"], 1100)
        self.assertEqual(account["interest_rate"], 0.0375)
        child = next(item for item in account_data if item["parent_account_id"] == account_id)
        self.assertEqual(child["asset_kind"], "gic")
        self.assertEqual(child["name"], "Route GIC")
        self.assertEqual(child["latest_amount"], 500)
        self.assertEqual(child["interest_rate"], 0.04)
        self.assertTrue(child["redeemable"])
        self.assertEqual(child["owner_details"], f"{owner_id}:1.0")
        self.assertEqual(self.client.post("/api/model/accounts", json={}).status_code, 400)

    def test_account_balance_api_preserves_decimal_text_until_cents_storage(self):
        with closing(sqlite3.connect(self.database)) as connection:
            person_id = connection.execute("SELECT id FROM people ORDER BY id LIMIT 1").fetchone()[
                0
            ]
        response = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Decimal boundary",
                "account_number": "DECIMAL-BOUNDARY",
                "category": "cash",
                "balance_amount": "100000000000000.01",
                "balance_date": "2026-09-28",
                "owners": [{"person_id": person_id, "share": 1}],
            },
        )

        self.assertEqual(response.status_code, 201)
        with closing(sqlite3.connect(self.database)) as connection:
            stored = connection.execute(
                """SELECT s.amount_cents
                   FROM balance_snapshots s
                   JOIN accounts a ON a.id = s.account_id
                   WHERE a.account_number = 'DECIMAL-BOUNDARY'"""
            ).fetchone()
        self.assertEqual(stored, (10000000000000001,))

    def test_new_canonical_balance_supersedes_legacy_snapshot_in_accounts_and_dashboard(self):
        from repositories.account_repository import AccountRepository
        from repositories.balance_snapshot_repository import BalanceSnapshotRepository

        before_gross = self.client.get("/api/dashboard").get_json()["gross_assets"]
        with self.runtime_config.connect() as connection:
            account = AccountRepository(connection).create(
                "Legacy dates", "non_registered", account_number="LEGACY-DATES"
            )
            BalanceSnapshotRepository(connection).add(account.id, "20260115", 1000)

        response = self.client.post(
            f"/api/model/accounts/{account.id}/balance",
            json={"date": "20260131", "amount": 900},
        )
        self.assertEqual(response.status_code, 201)
        accounts = self.client.get("/api/model/accounts").get_json()["accounts"]
        updated = next(item for item in accounts if item["id"] == account.id)
        self.assertEqual((updated["latest_date"], updated["latest_amount"]), ("2026-01-31", 900))
        after_gross = self.client.get("/api/dashboard").get_json()["gross_assets"]
        self.assertEqual(Decimal(str(after_gross)) - Decimal(str(before_gross)), Decimal("900"))

    def test_account_routes_reject_invalid_calendar_dates(self):
        owner_id = self._people()[0]["id"]
        invalid_create = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Invalid date",
                "category": "non_registered",
                "account_number": "INVALID-DATE",
                "start_date": "2026-02-30",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
        )
        self.assertEqual(invalid_create.status_code, 400)

        created = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Date boundary",
                "category": "non_registered",
                "account_number": "DATE-BOUNDARY",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
        )
        self.assertEqual(created.status_code, 201)
        account_id = created.get_json()["id"]

        invalid_update = self.client.put(
            f"/api/model/accounts/{account_id}",
            json={
                "name": "Date boundary",
                "account_number": "DATE-BOUNDARY",
                "asset_kind": "account",
                "maturity_date": "2026-13-01",
            },
        )
        self.assertEqual(invalid_update.status_code, 400)
        self.assertEqual(
            self.client.post(
                f"/api/model/accounts/{account_id}/balance",
                json={"date": "not-a-date", "amount": 100},
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                f"/api/model/accounts/{account_id}/gics",
                json={
                    "name": "Invalid GIC",
                    "principal": 100,
                    "interest_rate": 0.03,
                    "start_date": "2026-01-01",
                    "maturity_date": "2027-02-29",
                },
            ).status_code,
            400,
        )

    def test_invalid_money_inputs_return_clear_client_errors(self):
        account_id = self.client.get("/api/model/accounts").get_json()["accounts"][0]["id"]
        for amount in ("abc", "", "12,50", "inf"):
            with self.subTest(amount=amount):
                response = self.client.post(
                    f"/api/model/accounts/{account_id}/balance",
                    json={"date": "2026-09-28", "amount": amount},
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("Invalid amount", response.get_json()["error"])

    def test_real_estate_api_preserves_decimal_text_until_cents_storage(self):
        with closing(sqlite3.connect(self.database)) as connection:
            person_id = connection.execute("SELECT id FROM people ORDER BY id LIMIT 1").fetchone()[
                0
            ]
        response = self.client.post(
            "/api/model/real-estate",
            json={
                "name": "Decimal property",
                "estimated_value": "100000000000000.01",
                "acb": "90000000000000.005",
                "valuation_date": "2026-09-28",
                "owners": [{"person_id": person_id, "share": 1}],
            },
        )

        self.assertEqual(response.status_code, 201)
        with closing(sqlite3.connect(self.database)) as connection:
            stored = connection.execute(
                """SELECT estimated_value_cents, acb_cents
                   FROM real_estate_assets WHERE name = 'Decimal property'"""
            ).fetchone()
        self.assertEqual(stored, (10000000000000001, 9000000000000001))

    def test_account_can_be_updated(self):
        owner_id = self._people()[0]["id"]
        created = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Before",
                "category": "tfsa",
                "account_number": "UPDATE-001",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
        )
        account_id = created.get_json()["id"]
        updated = self.client.put(
            f"/api/model/accounts/{account_id}",
            json={
                "name": "After",
                "category": "tfsa",
                "account_number": "UPDATE-001",
                "asset_kind": "account",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
        )
        self.assertEqual(updated.status_code, 200)
        account = next(
            item
            for item in self.client.get("/api/model/accounts").get_json()["accounts"]
            if item["id"] == account_id
        )
        self.assertEqual(account["name"], "After")

    def test_account_lifecycle_validation_and_gic_owner_inheritance_through_api(self):
        owners = self._people()
        first_owner, second_owner = owners[0], owners[1]
        accounts_before = len(self.client.get("/api/model/accounts").get_json()["accounts"])

        invalid_accounts = (
            {"name": "Missing number", "category": "tfsa", "account_number": ""},
            {
                "name": "Unknown kind",
                "category": "tfsa",
                "account_number": "BAD-1",
                "asset_kind": "security",
            },
            {
                "name": "Orphan GIC",
                "category": "tfsa",
                "account_number": "",
                "asset_kind": "gic",
            },
            {
                "name": "Incomplete ownership",
                "category": "tfsa",
                "account_number": "BAD-OWNER",
                "owners": [{"person_id": first_owner["id"], "share": 0.5}],
            },
        )
        for payload in invalid_accounts:
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.client.post("/api/model/accounts", json=payload).status_code, 400
                )
        self.assertEqual(
            len(self.client.get("/api/model/accounts").get_json()["accounts"]), accounts_before
        )

        def create_parent(number, owner):
            response = self.client.post(
                "/api/model/accounts",
                json={
                    "name": number,
                    "category": "tfsa",
                    "account_number": number,
                    "institution": "Lifecycle Bank",
                    "owners": [{"person_id": owner["id"], "share": 1}],
                },
            )
            self.assertEqual(response.status_code, 201)
            return response.get_json()["id"]

        first_parent = create_parent("LIFE-PARENT-1", first_owner)
        second_parent = create_parent("LIFE-PARENT-2", second_owner)
        gic = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Lifecycle GIC",
                "category": "tfsa",
                "account_number": "",
                "asset_kind": "gic",
                "parent_account_id": first_parent,
                "principal": 1000,
                "start_date": "2026-01-01",
                "maturity_date": "2027-01-01",
            },
        )
        self.assertEqual(gic.status_code, 201)
        gic_id = gic.get_json()["id"]
        moved = self.client.put(
            f"/api/model/accounts/{gic_id}",
            json={
                "name": "Lifecycle GIC moved",
                "account_number": "",
                "asset_kind": "gic",
                "parent_account_id": second_parent,
                "principal": 1000,
                "start_date": "2026-01-01",
                "maturity_date": "2027-01-01",
            },
        )
        self.assertEqual(moved.status_code, 200)
        moved_account = next(
            item
            for item in self.client.get("/api/model/accounts").get_json()["accounts"]
            if item["id"] == gic_id
        )
        self.assertEqual(moved_account["parent_account_id"], second_parent)
        self.assertIn(second_owner["name"], moved_account["owners"])
        self.assertNotIn(first_owner["name"], moved_account["owners"])

        invalid_balance = self.client.post(
            f"/api/model/accounts/{first_parent}/balance",
            json={"date": "2026-01-01", "amount": -1, "interest_rate": -2},
        )
        self.assertEqual(invalid_balance.status_code, 400)

    def test_real_estate_create_update_and_projection_routes(self):
        owner_id = self._people()[0]["id"]
        created = self.client.post(
            "/api/model/real-estate",
            json={
                "name": "Route property",
                "estimated_value": 200000,
                "valuation_date": "2026-01-01",
                "property_type": "Property share",
                "acb": 150000,
                "owners": [{"person_id": owner_id, "share": 1}],
            },
        )
        self.assertEqual(created.status_code, 201)
        asset_id = created.get_json()["id"]
        updated = self.client.put(
            f"/api/model/real-estate/{asset_id}",
            json={
                "name": "Updated property",
                "estimated_value": 210000,
                "valuation_date": "2026-02-01",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
        )
        self.assertEqual(updated.status_code, 200)
        scenario = self.client.post(
            "/api/model/scenarios",
            json={"name": "Route scenario", "baseline_date": "2026-01-01", "growth_rate": "0.03"},
        )
        self.assertEqual(scenario.status_code, 201)
        projection = self.client.post(
            f"/api/model/real-estate/{asset_id}/projections",
            json={
                "projection_date": "2030-01-01",
                "projected_value": 250000,
                "scenario_id": scenario.get_json()["id"],
            },
        )
        self.assertEqual(projection.status_code, 201)
        assets = self.client.get("/api/model/real-estate").get_json()["assets"]
        self.assertEqual(
            next(item for item in assets if item["id"] == asset_id)["name"], "Updated property"
        )
        self.assertEqual(self.client.post("/api/model/real-estate", json={}).status_code, 400)

    def test_real_estate_validation_failures_are_atomic_through_api(self):
        owner_id = self._people()[0]["id"]
        invalid_payloads = (
            {
                "name": "",
                "estimated_value": 100,
                "valuation_date": "2026-01-01",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
            {
                "name": "Negative land",
                "estimated_value": -1,
                "valuation_date": "2026-01-01",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
            {
                "name": "Bad date",
                "estimated_value": 100,
                "valuation_date": "not-a-date",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
            {
                "name": "Incomplete ownership",
                "estimated_value": 100,
                "valuation_date": "2026-01-01",
                "owners": [{"person_id": owner_id, "share": 0.5}],
            },
        )
        before = len(self.client.get("/api/model/real-estate").get_json()["assets"])
        for payload in invalid_payloads:
            with self.subTest(name=payload["name"]):
                self.assertEqual(
                    self.client.post("/api/model/real-estate", json=payload).status_code,
                    400,
                )
        after = len(self.client.get("/api/model/real-estate").get_json()["assets"])
        self.assertEqual(after, before)

        valid = self.client.post(
            "/api/model/real-estate",
            json={
                "name": "Projection validation land",
                "estimated_value": 100000,
                "valuation_date": "2026-01-01",
                "owners": [{"person_id": owner_id, "share": 1}],
            },
        )
        asset_id = valid.get_json()["id"]
        for payload in (
            {"projection_date": "invalid", "projected_value": 110000},
            {"projection_date": "2030-01-01", "projected_value": -1},
            {
                "projection_date": "2030-01-01",
                "projected_value": 110000,
                "effective_tax_rate": 2,
            },
        ):
            with self.subTest(projection=payload):
                self.assertEqual(
                    self.client.post(
                        f"/api/model/real-estate/{asset_id}/projections", json=payload
                    ).status_code,
                    400,
                )
        self.assertEqual(
            self.client.put(
                "/api/model/real-estate/999999",
                json={
                    "name": "Missing",
                    "estimated_value": 100,
                    "valuation_date": "2026-01-01",
                    "owners": [{"person_id": owner_id, "share": 1}],
                },
            ).status_code,
            400,
        )

    def test_csv_transaction_import_route_and_queries(self):
        account_id = next(
            item["id"]
            for item in self.client.get("/api/model/accounts").get_json()["accounts"]
            if item["account_number"] == "SYN-SAV-001"
        )
        response = self.client.post(
            "/api/model/transactions/import",
            data={
                "account_id": str(account_id),
                "files": (
                    io.BytesIO(b"Date,Amount,Description\n2026-09-10,12.34,Route test\n"),
                    "route.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["imported"], 1)
        transactions = self.client.get(
            f"/api/model/transactions?account_id={account_id}"
        ).get_json()["transactions"]
        self.assertTrue(any(item["description"] == "Route test" for item in transactions))
        self.assertGreaterEqual(
            len(self.client.get("/api/model/import-history").get_json()["imports"]), 1
        )
        self.assertEqual(
            self.client.post("/api/model/transactions/import", data={}).status_code, 400
        )

    def test_localized_import_failure_preserves_file_context_and_rolls_back(self):
        account_id = self.client.get("/api/model/accounts").get_json()["accounts"][0]["id"]
        original_people = self._people()

        def reject_after_write(connection, *_args, **_kwargs):
            PersonRepository(connection).create("Must be rolled back")
            raise ValidationError("person_required", "Person is required")

        for locale in ("en-CA", "fr-CA"):
            with self.subTest(locale=locale):
                self.app.extensions["localization"].select(locale)
                before = self.database.read_bytes()
                with patch("web.transaction_routes._import_csv", reject_after_write):
                    response = self.client.post(
                        "/api/model/transactions/import",
                        data={
                            "account_id": str(account_id),
                            "files": (io.BytesIO(b"synthetic"), "Original evidence.csv"),
                        },
                        content_type="multipart/form-data",
                    )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error_code"], "person_required")
                self.assertEqual(response.get_json()["error_language"], locale)
                self.assertTrue(response.get_json()["error"].startswith("Original evidence.csv:"))
                self.assertEqual(self._people(), original_people)
                self.assertEqual(self.database.read_bytes(), before)

    def test_supported_document_matrix_imports_through_http_routes(self):
        fixtures = self.runtime / "fixtures"
        matrix_runtime = self.runtime / "http-matrix"
        matrix_runtime.mkdir()
        (matrix_runtime / "finance.config.json").write_text(
            (self.runtime / "finance.config.json").read_text()
        )
        with closing(sqlite3.connect(matrix_runtime / "finance.sqlite3")) as connection:
            application.ensure_domain_schema(connection)
            connection.execute(
                "INSERT INTO people(name, birth_date) VALUES ('HTTP Matrix Owner', '1970-01-01')"
            )
            connection.commit()
        self._use_runtime(RuntimeConfig.load(matrix_runtime))
        owner_id = self._people()[0]["id"]

        def create_test_account(name, category, account_number, institution):
            response = self.client.post(
                "/api/model/accounts",
                json={
                    "name": name,
                    "category": category,
                    "account_number": account_number,
                    "institution": institution,
                    "owners": [{"person_id": owner_id, "share": 1}],
                },
            )
            self.assertEqual(response.status_code, 201)
            return response.get_json()["id"]

        def upload(account_id, filename, **fields):
            path = fixtures / filename
            return self.client.post(
                "/api/model/transactions/import",
                data={
                    "account_id": str(account_id),
                    "files": (io.BytesIO(path.read_bytes()), path.name),
                    **fields,
                },
                content_type="multipart/form-data",
            )

        eq_account = create_test_account(
            "PDF transaction rows", "non_registered", "999-888-777", "EQ"
        )
        eq = upload(eq_account, "eq-monthly-statement.pdf")
        self.assertEqual(eq.status_code, 201)
        self.assertEqual(eq.get_json()["imported"], 3)

        achieva_account = create_test_account("PDF GIC TR", "tfsa", "SYN-ACH-001", "Achieva")
        achieva = upload(achieva_account, "achieva-gic-history.pdf")
        self.assertEqual(achieva.status_code, 201)
        self.assertEqual(achieva.get_json()["imported"], 2)

        pending_manulife = upload("auto", "manulife-rrsp-statement.pdf")
        self.assertEqual(pending_manulife.status_code, 409)
        self.assertTrue(pending_manulife.get_json()["confirm_account_creation"])
        manulife = upload("auto", "manulife-rrsp-statement.pdf", confirm_account_creation="1")
        self.assertEqual(manulife.status_code, 201)
        self.assertEqual(manulife.get_json()["imported"], 4)

        rbc_account = create_test_account(
            "CSV + PDF reconciliation",
            "non_registered",
            "99999-8888888",
            "RBC",
        )
        rbc_csv = upload(rbc_account, "rbc-canada.csv")
        self.assertEqual(rbc_csv.status_code, 201)
        rbc_statement = upload(rbc_account, "rbc-deposit-statement.pdf")
        self.assertEqual(rbc_statement.status_code, 201)
        reconciliation = rbc_statement.get_json()["results"][0]
        self.assertEqual(reconciliation["reconciliation_status"], "reconciled")
        self.assertEqual(reconciliation["difference"], 0)

        accounts = self.client.get("/api/model/accounts").get_json()["accounts"]
        institutions = {item["institution"] for item in accounts}
        self.assertTrue({"EQ", "Achieva", "Manulife", "RBC"}.issubset(institutions))
        holdings = self.client.get("/api/model/holdings").get_json()["holdings"]
        self.assertTrue(
            any(
                item["institution"] == "Manulife" and item["fund_code"] == "1234"
                for item in holdings
            )
        )

    def test_read_model_endpoints_return_expected_envelopes(self):
        endpoints = {
            "/api/dashboard": "gross_assets",
            "/api/model/accounts": "accounts",
            "/api/model/holdings": "holdings",
            "/api/model/transactions": "transactions",
            "/api/model/import-history": "imports",
            "/api/model/annual-summary": "summary",
        }
        for path, key in endpoints.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(key, response.get_json())

    def test_holdings_route_filters_by_account(self):
        from repositories.investment_holding_repository import InvestmentHoldingRepository

        with closing(sqlite3.connect(self.database)) as connection:
            person_id = connection.execute("SELECT id FROM people ORDER BY id LIMIT 1").fetchone()[
                0
            ]
        created = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Holdings account",
                "account_number": "HOLD-1",
                "category": "rrsp",
                "owners": [{"person_id": person_id, "share": 1}],
            },
        )
        self.assertEqual(created.status_code, 201)
        account_id = created.get_json()["id"]
        with closing(sqlite3.connect(self.database)) as connection:
            InvestmentHoldingRepository(connection).upsert(
                account_id, "2026-09-01", "Equity", "HOLD", "Held Fund", 1, 10, 10, None, "test"
            )
            connection.commit()

        response = self.client.get(f"/api/model/holdings?account_id={account_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["fund_code"] for item in response.get_json()["holdings"]], ["HOLD"])

    def test_import_into_reconciled_period_asks_for_confirmation(self):
        with closing(sqlite3.connect(self.database)) as connection:
            person_id = connection.execute("SELECT id FROM people ORDER BY id LIMIT 1").fetchone()[
                0
            ]
        created = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Locked account",
                "account_number": "RECON-LOCK",
                "category": "non_registered",
                "owners": [{"person_id": person_id, "share": 1}],
            },
        )
        account_id = created.get_json()["id"]

        def upload(content, name, **fields):
            return self.client.post(
                "/api/model/transactions/import",
                data={
                    "account_id": str(account_id),
                    "files": (io.BytesIO(content), name),
                    **fields,
                },
                content_type="multipart/form-data",
            )

        header = b"Date,Description,Amount,Balance\n"
        self.assertEqual(upload(header + b"2026-01-05,Pay,1000,1000\n", "jan.csv").status_code, 201)
        reconciled = self.client.post(
            f"/api/model/accounts/{account_id}/reconcile",
            json={"date": "2026-01-31", "amount": 1000},
        )
        self.assertEqual(reconciled.get_json()["reconciled_through"], "2026-01-31")
        late = header + b"2026-01-25,Refund,50,1050\n"

        refused = upload(late, "late.csv")

        self.assertEqual(refused.status_code, 409)
        body = refused.get_json()
        self.assertTrue(body["confirm_reconciled"])
        self.assertEqual((body["reconciled_through"], body["transaction_count"]), ("2026-01-31", 1))

        confirmed = upload(late, "late.csv", confirm_reconciled="1")

        self.assertEqual(confirmed.status_code, 201)
        [flag] = confirmed.get_json()["results"][0]["reconciled_periods_needing_review"]
        self.assertEqual((flag["reconciled_through"], flag["difference"]), ("2026-01-31", 50.0))
        status = self.client.get(f"/api/model/accounts/{account_id}/reconciliation").get_json()
        self.assertEqual(
            (status["reconciled_through"], status["needs_review"]), ("2026-01-31", True)
        )

    def test_manual_reconciliation_route_and_opening_balance_response(self):
        with closing(sqlite3.connect(self.database)) as connection:
            person_id = connection.execute("SELECT id FROM people ORDER BY id LIMIT 1").fetchone()[
                0
            ]
        created = self.client.post(
            "/api/model/accounts",
            json={
                "name": "Reconciled account",
                "account_number": "RECON-1",
                "category": "non_registered",
                "balance_amount": 250,
                "balance_date": "2026-09-01",
                "owners": [{"person_id": person_id, "share": 1}],
            },
        )
        self.assertEqual(created.status_code, 201)
        account_id = created.get_json()["id"]
        transactions = self.client.get(
            f"/api/model/transactions?account_id={account_id}"
        ).get_json()
        self.assertEqual(transactions["opening_balances"][0]["balance_after"], 250)

        response = self.client.post(
            f"/api/model/accounts/{account_id}/reconcile",
            json={"date": "2026-09-02", "amount": 275},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["difference"], 25)
        invalid = self.client.post(
            f"/api/model/accounts/{account_id}/reconcile",
            json={"date": "invalid", "amount": 1},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_questrade_status_connect_refresh_and_sync_route_errors(self):
        status = self.client.get("/api/questrade/status")
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.get_json()["connected"])
        self.assertEqual(
            self.client.get("/api/questrade/connect?connection=missing").status_code, 503
        )
        refresh = self.client.post("/api/questrade/refresh?connection=missing")
        self.assertEqual(refresh.status_code, 302)
        sync = self.client.post("/api/questrade/sync", json={"connection": "missing"})
        self.assertEqual(sync.status_code, 502)
        self.assertIn("not connected", sync.get_json()["errors"][0]["error"])

    def test_questrade_connect_sets_state_and_redirects(self):
        with self._questrade_logins("alex"):
            response = self.client.get("/api/questrade/connect?connection=alex")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.startswith(AUTHORIZE_URL))
        with self.client.session_transaction() as session:
            self.assertEqual(session["questrade_oauth_state"]["connection"], "alex")

    def test_questrade_connect_requires_a_configured_redirect_uri(self):
        runtime = self.runtime_config.with_values(
            QUESTRADE_REDIRECT_URI=None,
            QUESTRADE_CONNECTIONS=[{"name": "alex", "consumer_key": "synthetic-key"}],
        )
        with self._serving(runtime):
            response = self.client.get("/api/questrade/connect?connection=alex")
        self.assertEqual(response.status_code, 503)
        self.assertIn("QUESTRADE_REDIRECT_URI", response.get_json()["error"])

    def test_questrade_callback_rejects_bad_state_and_stores_valid_tokens(self):
        self.assertEqual(self.client.get("/questrade/callback?code=x&state=bad").status_code, 400)
        token_payload = {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "api_server": "https://api01.iq.questrade.com/",
            "expires_in": 1800,
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(token_payload).encode()

        with self.client.session_transaction() as session:
            session["questrade_oauth_state"] = {"value": "expected", "connection": "alex"}
        with (
            self._questrade_logins("alex"),
            patch.object(application.urllib.request, "urlopen", return_value=Response()),
        ):
            response = self.client.get("/questrade/callback?code=code&state=expected")
        self.assertEqual(response.status_code, 302)
        self.assertIn("questrade=connected", response.location)
        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute(
                "SELECT name, api_server FROM questrade_authorizations"
            ).fetchone()
        self.assertEqual(row, ("alex", "https://api01.iq.questrade.com/"))

    def test_questrade_sync_creates_account_holdings_balance_and_activity(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                """INSERT INTO questrade_authorizations(
                       name, access_token, refresh_token, api_server, access_expires_at
                ) VALUES ('alex', 'unused', 'unused', 'https://api01.iq.questrade.com/', NULL)"""
            )
            connection.commit()

        activity_returned = False

        def api_response(_row, path):
            nonlocal activity_returned
            if path == "/v1/accounts":
                return {"accounts": [{"number": "SYN-QT-001", "type": "TFSA"}, {"type": "TFSA"}]}
            if path.endswith("/balances"):
                return {"combinedBalances": [{"currency": "CAD", "totalEquity": 1200}]}
            if path.endswith("/positions"):
                return {
                    "positions": [
                        {
                            "symbol": "SYN",
                            "openQuantity": 10,
                            "currentPrice": 100,
                            "currentMarketValue": 1000,
                        }
                    ]
                }
            if "/executions?" in path:
                return {"executions": [{"id": 1}]}
            if "/activities?" in path and not activity_returned:
                activity_returned = True
                return {
                    "activities": [
                        {
                            "transactionDate": "2026-09-01T12:00:00Z",
                            "netAmount": 0,
                            "grossAmount": 12.34,
                            "type": "Dividend",
                            "action": "Reinvest",
                            "symbol": "SYN",
                            "description": "Synthetic reinvestment",
                        }
                    ]
                }
            return {"activities": []}

        with (
            patch.object(QuestradeClient, "refresh_expiring_authorizations"),
            patch.object(QuestradeClient, "api_get", side_effect=api_response),
        ):
            result = self._questrade().synchronize("alex")
        self.assertEqual(result["account_count"], 2)
        self.assertEqual(result["balance_count"], 1)
        self.assertEqual(result["position_count"], 1)
        self.assertEqual(result["execution_count"], 1)
        self.assertEqual(result["transaction_count"], 1)
        with closing(sqlite3.connect(self.database)) as connection:
            account = connection.execute(
                "SELECT id, account_type FROM accounts WHERE external_account_id = 'SYN-QT-001'"
            ).fetchone()
            holding = connection.execute(
                "SELECT market_value FROM investment_holdings WHERE account_id = ?", (account[0],)
            ).fetchone()
            transaction = connection.execute(
                "SELECT amount FROM transactions WHERE account_id = ?", (account[0],)
            ).fetchone()
        self.assertEqual(account[1], "tfsa")
        self.assertEqual(holding[0], 1000)
        self.assertEqual(transaction[0], 12.34)

    def test_questrade_route_replays_family_sync_idempotently_and_updates_state(self):
        scenarios = json.loads(
            (Path(__file__).parent / "fixtures/questrade/sync_scenarios.json").read_text()
        )
        with self.runtime_config.connect() as connection:
            connection.executemany(
                """INSERT INTO questrade_authorizations(
                       name, access_token, refresh_token, api_server, access_expires_at
                   ) VALUES (?, 'unused', 'unused', 'https://api01.iq.questrade.com/', NULL)""",
                [("primary",), ("secondary",)],
            )

        def synchronize(scenario):
            with (
                self._questrade_logins("primary", "secondary"),
                patch.object(QuestradeClient, "refresh_expiring_authorizations"),
                patch.object(
                    QuestradeClient,
                    "api_get",
                    side_effect=SyntheticQuestradeAPI(scenario),
                ),
            ):
                response = self.client.post("/api/questrade/sync", json={})
            self.assertEqual(response.status_code, 200)
            return response.get_json()

        first = synchronize(scenarios["initial"])
        self.assertEqual(
            {item["connection"] for item in first["results"]}, {"primary", "secondary"}
        )
        self.assertEqual(sum(item["account_count"] for item in first["results"]), 4)
        self.assertEqual(sum(item["transaction_count"] for item in first["results"]), 3)

        repeated = synchronize(scenarios["initial"])
        self.assertEqual(sum(item["transaction_count"] for item in repeated["results"]), 0)

        updated = synchronize(scenarios["updated"])
        self.assertEqual(sum(item["transaction_count"] for item in updated["results"]), 2)
        dashboard = self.client.get("/api/dashboard").get_json()
        uninvested = {
            item["account_number"]: item["amount"]
            for item in dashboard["uninvested_security_accounts"]
            if item["institution"] == "Questrade"
        }
        self.assertEqual(
            uninvested,
            {
                "SYN-QT-CASH-001": 24990,
                "SYN-QT-RRSP-001": 100000,
                "SYN-QT-TFSA-001": 20000,
                "SYN-QT-TFSA-002": 5000,
            },
        )

        with self.runtime_config.connect() as connection:
            linked_accounts = connection.execute(
                """SELECT account_number, account_type FROM accounts
                   WHERE external_provider = 'questrade' ORDER BY account_number"""
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in linked_accounts],
                [
                    ("SYN-QT-CASH-001", "non_registered"),
                    ("SYN-QT-RRSP-001", "rrsp"),
                    ("SYN-QT-TFSA-001", "tfsa"),
                    ("SYN-QT-TFSA-002", "tfsa"),
                ],
            )
            balances = dict(
                connection.execute(
                    """SELECT a.account_number, s.amount FROM balance_snapshots s
                       JOIN accounts a ON a.id = s.account_id
                       WHERE a.external_provider = 'questrade'"""
                ).fetchall()
            )
            self.assertEqual(balances["SYN-QT-CASH-001"], 24990)
            self.assertEqual(balances["SYN-QT-TFSA-001"], 122000)
            holdings = connection.execute(
                """SELECT a.account_number, h.fund_code, h.market_value
                   FROM investment_holdings h JOIN accounts a ON a.id = h.account_id
                   WHERE a.external_provider = 'questrade'
                   ORDER BY a.account_number, h.fund_code"""
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in holdings],
                [
                    ("SYN-QT-RRSP-001", "EQUITY.TO", 205000),
                    ("SYN-QT-TFSA-001", "XEQT.TO", 102000),
                    ("SYN-QT-TFSA-002", "VBAL.TO", 76000),
                ],
            )
            transactions = connection.execute(
                """SELECT a.account_number, t.description, t.amount
                   FROM transactions t JOIN accounts a ON a.id = t.account_id
                   WHERE a.external_provider = 'questrade'
                   ORDER BY a.account_number, t.transaction_date"""
            ).fetchall()
            self.assertEqual(len(transactions), 5)
            self.assertIn(
                ("SYN-QT-RRSP-001", "Synthetic reinvested distribution", 42.5),
                [tuple(row) for row in transactions],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM questrade_authorizations WHERE last_sync_at IS NOT NULL"
                ).fetchone()[0],
                2,
            )

    def test_questrade_sync_route_reports_partial_success(self):
        def sync(name):
            if name == "bad":
                raise RuntimeError("synthetic failure")
            return {"connection": name, "account_count": 1}

        with (
            self._questrade_logins("bad", "good"),
            patch.object(QuestradeConnectionProvider, "synchronize", side_effect=sync),
        ):
            response = self.client.post("/api/questrade/sync", json={})
        self.assertEqual(response.status_code, 207)
        self.assertEqual(response.get_json()["results"][0]["connection"], "good")
        self.assertEqual(response.get_json()["errors"][0]["connection"], "bad")

    def test_questrade_sync_route_exposes_component_failures(self):
        result = {
            "connection": "alex",
            "account_count": 1,
            "errors": [
                {"account": "QT-1", "component": "positions", "error": "service unavailable"}
            ],
        }
        with (
            self._questrade_logins("alex"),
            patch.object(QuestradeConnectionProvider, "synchronize", return_value=result),
        ):
            response = self.client.post("/api/questrade/sync", json={})

        self.assertEqual(response.status_code, 207)
        self.assertEqual(
            response.get_json()["errors"][0],
            {
                "connection": "alex",
                "account": "QT-1",
                "component": "positions",
                "error": "service unavailable",
            },
        )

    def test_questrade_sync_route_passes_a_refetch_date(self):
        with (
            self._questrade_logins("alex"),
            patch.object(
                QuestradeConnectionProvider,
                "synchronize",
                return_value={"connection": "alex", "account_count": 1},
            ) as synchronize,
        ):
            response = self.client.post(
                "/api/questrade/sync", json={"connection": "alex", "fetch_from": "2025-06-01"}
            )

        self.assertEqual(response.status_code, 200)
        synchronize.assert_called_once_with("alex", fetch_from="2025-06-01")

    def test_questrade_sync_retries_api_call_once_after_unauthorized_response(self):
        with self.runtime_config.connect() as connection:
            connection.execute(
                """INSERT INTO questrade_authorizations(
                       name, access_token, refresh_token, api_server, access_expires_at
                   ) VALUES ('alex', 'unused', 'unused',
                             'https://api01.iq.questrade.com/', NULL)"""
            )
        responses = [QuestradeUnauthorized("Questrade API request failed (401)"), {"accounts": []}]
        with (
            patch.object(QuestradeClient, "refresh_expiring_authorizations"),
            patch.object(QuestradeClient, "refresh_authorization") as refresh,
            patch.object(QuestradeClient, "api_get", side_effect=responses) as api_get,
        ):
            result = self._questrade().synchronize("alex")
        self.assertEqual(result["account_count"], 0)
        self.assertEqual(api_get.call_count, 2)
        refresh.assert_called_once()

    def test_questrade_url_validation_rejects_non_https_and_foreign_hosts(self):
        self.assertEqual(
            QuestradeClient.validate_url("https://api01.iq.questrade.com/v1/accounts"),
            "https://api01.iq.questrade.com/v1/accounts",
        )
        for url in ("http://api01.iq.questrade.com/v1/accounts", "https://example.com/v1"):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                QuestradeClient.validate_url(url)

    def test_runtime_configuration_helpers_cover_profiles_and_invalid_config(self):
        self.assertEqual(application.profile_data_dir("dev"), application.PROFILE_DATA_DIRS["dev"])
        with self.assertRaisesRegex(ValueError, "Unknown runtime profile"):
            application.profile_data_dir("missing")
        with patch.dict(application.os.environ, {"SYNTHETIC_SETTING": "from-env"}):
            self.assertEqual(self.runtime_config.setting("SYNTHETIC_SETTING"), "from-env")
        configured = RuntimeConfig(
            self.runtime,
            {
                "QUESTRADE_CONNECTIONS": [
                    {"name": "alex", "consumer_key": "key", "client_secret": "secret"},
                    {"name": "ignored"},
                ],
                "QUESTRADE_CONSUMER_KEY": "legacy",
            },
        )
        profiles = QuestradeSettings.from_runtime(configured.context()).profiles
        self.assertEqual(profiles["alex"]["client_secret"], "secret")
        self.assertEqual(profiles["default"]["consumer_key"], "legacy")

        invalid = self.runtime / "invalid-runtime"
        invalid.mkdir()
        (invalid / "finance.config.json").write_text("not-json")
        with self.assertRaisesRegex(RuntimeError, "Could not read"):
            RuntimeConfig.load(invalid)
        (invalid / "finance.config.json").write_text("[]")
        with self.assertRaisesRegex(RuntimeError, "JSON object"):
            RuntimeConfig.load(invalid)

    def _insert_authorization(self, name="alex", expires_at=None):
        cipher = self._questrade().settings.cipher()
        with self.runtime_config.connect() as connection:
            connection.execute(
                """INSERT INTO questrade_authorizations(
                       name, access_token, refresh_token, api_server, access_expires_at
                   ) VALUES (?, ?, ?, ?, ?)""",
                (
                    name,
                    cipher.encrypt(b"old-access").decode(),
                    cipher.encrypt(b"old-refresh").decode(),
                    "https://api01.iq.questrade.com/",
                    expires_at,
                ),
            )

    def test_questrade_token_refresh_updates_encrypted_tokens(self):
        self._insert_authorization()
        payload = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "api_server": "https://api02.iq.questrade.com/",
            "expires_in": 900,
            "refresh_token_expires_at": "2026-10-01T00:00:00+00:00",
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(payload).encode()

        with self.runtime_config.connect() as connection:
            row = self._stored_authorization(connection)
            with patch.object(application.urllib.request, "urlopen", return_value=Response()):
                self._questrade().client.refresh_authorization(connection, row)
            updated = connection.execute(
                "SELECT access_token, refresh_token, api_server FROM questrade_authorizations WHERE name = 'alex'"
            ).fetchone()
        cipher = self._questrade().settings.cipher()
        self.assertEqual(cipher.decrypt(updated[0].encode()), b"new-access")
        self.assertEqual(cipher.decrypt(updated[1].encode()), b"new-refresh")
        self.assertEqual(updated[2], "https://api02.iq.questrade.com/")

    def test_questrade_refresh_reports_http_and_network_failures(self):
        self._insert_authorization()
        with self.runtime_config.connect() as connection:
            row = self._stored_authorization(connection)
            http_error = urllib.error.HTTPError(
                TOKEN_URL, 400, "bad", {}, io.BytesIO(b"synthetic detail")
            )
            with patch.object(application.urllib.request, "urlopen", side_effect=http_error):
                with self.assertRaisesRegex(
                    RuntimeError, "refresh failed.*request rejected"
                ) as caught:
                    self._questrade().client.refresh_authorization(connection, row)
                self.assertNotIn("synthetic detail", str(caught.exception))
            with patch.object(
                application.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("offline"),
            ):
                with self.assertRaisesRegex(RuntimeError, "refresh failed"):
                    self._questrade().client.refresh_authorization(connection, row)

    def test_questrade_api_get_decodes_json_and_reports_failures(self):
        self._insert_authorization()

        class Response:
            def __init__(self, payload=b'{"accounts": []}'):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return self.payload

        with self.runtime_config.connect() as connection:
            row = self._stored_authorization(connection)
            with patch.object(application.urllib.request, "urlopen", return_value=Response()):
                self.assertEqual(
                    self._questrade().client.api_get(row, "/v1/accounts"), {"accounts": []}
                )
            for status, detail in ((401, b"expired"), (429, b"rate limited"), (500, b"down")):
                http_error = urllib.error.HTTPError(
                    "https://api01.iq.questrade.com/v1/accounts",
                    status,
                    "synthetic error",
                    {},
                    io.BytesIO(detail),
                )
                with (
                    self.subTest(status=status),
                    patch.object(application.urllib.request, "urlopen", side_effect=http_error),
                    self.assertRaisesRegex(RuntimeError, rf"\({status}\)"),
                ):
                    self._questrade().client.api_get(row, "/v1/accounts")
            with patch.object(
                application.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("offline"),
            ):
                with self.assertRaisesRegex(RuntimeError, "API request failed"):
                    self._questrade().client.api_get(row, "/v1/accounts")
            with patch.object(
                application.urllib.request,
                "urlopen",
                return_value=Response(b"not-json"),
            ):
                with self.assertRaisesRegex(RuntimeError, "API request failed"):
                    self._questrade().client.api_get(row, "/v1/accounts")

    def test_only_expiring_valid_questrade_authorizations_are_refreshed(self):
        now = datetime.now(UTC)
        self._insert_authorization("missing-expiry")
        self._insert_authorization("invalid-expiry", "not-a-date")
        self._insert_authorization("future", (now + timedelta(hours=1)).isoformat())
        self._insert_authorization("expired", (now - timedelta(minutes=1)).isoformat())
        with self.runtime_config.connect() as connection:
            with patch.object(QuestradeClient, "refresh_authorization") as refresh:
                self._questrade().client.refresh_expiring_authorizations(connection)
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(refresh.call_args.args[1].name, "expired")

    def test_questrade_status_is_read_only_and_hides_legacy_diagnostics(self):
        self._insert_authorization("bad", "2020-01-01T00:00:00+00:00")
        self._insert_authorization("good", "2099-01-01T00:00:00+00:00")
        with self.runtime_config.connect() as connection:
            repository = QuestradeAuthorizationRepository(connection)
            repository.mark_failed("bad", "2026-01-01T00:00:00+00:00", "secret upstream token")
            before = repository.list_all()
        with (
            self._questrade_logins("bad", "good"),
            patch.object(QuestradeClient, "refresh_authorization") as refresh,
        ):
            for path in ("/api/questrade/status", "/api/connections/questrade/status"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.get_json()["authorizations"]), 2)
                self.assertNotIn("secret upstream token", response.get_data(as_text=True))
                self.assertEqual(
                    response.get_json()["authorizations"][0]["error_code"],
                    "questrade_connection_failed",
                )
            refresh.assert_not_called()
        with self.runtime_config.connect() as connection:
            self.assertEqual(QuestradeAuthorizationRepository(connection).list_all(), before)

    def test_questrade_failed_refresh_is_isolated_localized_and_preserves_rotated_tokens(self):
        expired = "2020-01-01T00:00:00+00:00"
        self._insert_authorization("bad", expired)
        self._insert_authorization("good", expired)
        with self.runtime_config.connect() as connection:
            before = self._stored_authorization(connection, "bad")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"access_token":"rotated-access","refresh_token":"rotated-refresh","expires_in":1800}'

        self.app.extensions["localization"].select("fr-CA")
        error = urllib.error.HTTPError(
            TOKEN_URL,
            400,
            "secret",
            {},
            io.BytesIO(b'{"error":"invalid_grant","error_description":"secret"}'),
        )
        with (
            self._questrade_logins("bad", "good"),
            patch.object(
                application.urllib.request, "urlopen", side_effect=[error, Response()]
            ) as request,
            patch.object(QuestradeClient, "api_get", return_value={"accounts": []}),
        ):
            result = self.client.post("/api/connections/questrade/sync", json={})
            self.assertEqual(result.status_code, 207)
            failure = result.get_json()["errors"][0]
            self.assertEqual(failure["error_code"], "questrade_authorization_rejected")
            self.assertEqual(failure["error_language"], "fr-CA")
            self.assertNotIn("secret", result.get_data(as_text=True))
            self.assertEqual(result.get_json()["results"][0]["connection"], "good")
            self.assertEqual(request.call_count, 2)
            for _ in range(2):
                status = self.client.get("/api/connections/questrade/status")
                self.assertEqual(status.status_code, 200)
            self.assertEqual(request.call_count, 2)
        with self.runtime_config.connect() as connection:
            bad = self._stored_authorization(connection, "bad")
            good = self._stored_authorization(connection, "good")
        self.assertEqual(
            (bad.access_token, bad.refresh_token), (before.access_token, before.refresh_token)
        )
        cipher = self._questrade().settings.cipher()
        self.assertEqual(cipher.decrypt(good.refresh_token.encode()), b"rotated-refresh")
        self.assertIsNone(good.last_sync_error)

    def test_component_refresh_failures_keep_codes_and_do_not_retry(self):
        self._insert_authorization("bad")
        self._insert_authorization("good")
        components = ("balances", "positions", "executions", "activities")
        for language in ("en-CA", "fr-CA"):
            self.app.extensions["localization"].select(language)
            for component in components:
                for rejected in (True, False):
                    with self.subTest(language=language, component=component, rejected=rejected):
                        calls = []

                        def api(authorization, path, *, calls=calls, component=component):
                            calls.append((authorization.name, path))
                            if path == "/v1/accounts":
                                return (
                                    {"accounts": [{"number": "SYNTH-1", "type": "TFSA"}]}
                                    if authorization.name == "bad"
                                    else {"accounts": []}
                                )
                            if f"/{component}" in path:
                                raise QuestradeUnauthorized("expired")
                            if "/balances" in path:
                                return {
                                    "combinedBalances": [{"currency": "CAD", "totalEquity": 100}]
                                }
                            return {}

                        error = (
                            urllib.error.HTTPError(
                                TOKEN_URL,
                                400,
                                "private",
                                {},
                                io.BytesIO(b'{"error":"invalid_grant"}'),
                            )
                            if rejected
                            else urllib.error.URLError("private")
                        )
                        with self.runtime_config.connect() as connection:
                            before = self._stored_authorization(connection, "bad")
                        with (
                            self._questrade_logins("bad", "good"),
                            patch.object(QuestradeClient, "api_get", side_effect=api),
                            patch.object(
                                application.urllib.request, "urlopen", side_effect=error
                            ) as refresh,
                        ):
                            response = self.client.post("/api/connections/questrade/sync", json={})
                            self.assertEqual(response.status_code, 207)
                            self.assertEqual(refresh.call_count, 1)
                            status = self.client.get("/api/connections/questrade/status").get_json()
                            self.assertEqual(refresh.call_count, 1)
                        expected = (
                            "questrade_authorization_rejected"
                            if rejected
                            else "questrade_refresh_unavailable"
                        )
                        data = response.get_json()
                        self.assertEqual(data["results"][0]["status"], "partial")
                        self.assertEqual(data["results"][1]["status"], "success")
                        self.assertEqual(
                            data["results"][0]["balance_count"], 0 if component == "balances" else 1
                        )
                        for detail in data["errors"] + data["results"][0]["errors"]:
                            self.assertEqual(detail["error_code"], expected)
                            self.assertEqual(detail["error_language"], language)
                        self.assertNotIn("private", response.get_data(as_text=True))
                        bad_calls = [path for name, path in calls if name == "bad"]
                        self.assertIn(f"/{component}", bad_calls[-1])
                        self.assertEqual(status["authorizations"][0]["error_code"], expected)
                        with self.runtime_config.connect() as connection:
                            after = self._stored_authorization(connection, "bad")
                        self.assertEqual(
                            (before.access_token, before.refresh_token),
                            (after.access_token, after.refresh_token),
                        )
                        self.assertEqual(after.last_sync_error, expected)

    def test_questrade_refresh_failure_classification_and_no_credential_changes(self):
        self._insert_authorization(expires_at="2020-01-01T00:00:00+00:00")
        self.app.extensions["localization"].select("fr-CA")
        cases = [
            (400, b"private response", "questrade_refresh_rejected"),
            (503, b"private response", "questrade_refresh_unavailable"),
            (429, b"private response", "questrade_refresh_unavailable"),
            (400, b"[]", "questrade_refresh_rejected"),
            (400, b'{"error":"invalid_grant"}', "questrade_authorization_rejected"),
        ]
        with self.runtime_config.connect() as connection:
            before = self._stored_authorization(connection)
        for status, body, code in cases:
            with self.subTest(status=status, body=body):
                error = urllib.error.HTTPError(TOKEN_URL, status, "private", {}, io.BytesIO(body))
                with (
                    self._questrade_logins("alex"),
                    patch.object(application.urllib.request, "urlopen", side_effect=error),
                ):
                    response = self.client.post(
                        "/api/connections/questrade/sync", json={"connection": "alex"}
                    )
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.get_json()["errors"][0]["error_code"], code)
                self.assertNotIn("private", response.get_data(as_text=True))
        with (
            self._questrade_logins("alex"),
            patch.object(
                application.urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("private token"),
            ),
        ):
            response = self.client.post("/api/connections/questrade/refresh?connection=alex")
            self.assertEqual(response.status_code, 302)
            self.assertNotIn("private", response.location)
            status = self.client.get("/api/connections/questrade/status").get_json()
            self.assertEqual(
                status["authorizations"][0]["error_code"], "questrade_refresh_unavailable"
            )
        with self.runtime_config.connect() as connection:
            after = self._stored_authorization(connection)
        self.assertEqual(
            (before.access_token, before.refresh_token), (after.access_token, after.refresh_token)
        )

    def test_questrade_malformed_refresh_responses_preserve_credentials_and_recovery_clears_error(
        self,
    ):
        self._insert_authorization()

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return self.payload

        with self.runtime_config.connect() as connection:
            before = self._stored_authorization(connection)
        invalid = [
            b"not-json",
            b"[]",
            b"{}",
            b'{"access_token":123}',
            b'{"access_token":"new","expires_in":-1}',
            b'{"access_token":"new","api_server":"https://example.com"}',
            b'{"access_token":"new","refresh_token_expires_at":{}}',
        ]
        for payload in invalid:
            with (
                self.subTest(payload=payload),
                patch.object(application.urllib.request, "urlopen", return_value=Response(payload)),
            ):
                response = self.client.post("/api/connections/questrade/refresh?connection=alex")
                self.assertEqual(response.status_code, 302)
                self.assertIn("questrade=error", response.location)
                with self.runtime_config.connect() as connection:
                    row = self._stored_authorization(connection)
                    self.assertEqual(
                        (row.access_token, row.refresh_token),
                        (before.access_token, before.refresh_token),
                    )
                    self.assertEqual(row.last_sync_error, "questrade_refresh_invalid")
        with patch.object(
            application.urllib.request,
            "urlopen",
            return_value=Response(b'{"access_token":"new","refresh_token":"rotated"}'),
        ):
            response = self.client.post("/api/connections/questrade/refresh?connection=alex")
        self.assertIn("questrade=refreshed", response.location)
        with self.runtime_config.connect() as connection:
            row = self._stored_authorization(connection)
            self.assertIsNone(row.last_sync_error)
            self.assertIsNone(row.last_sync_at)


if __name__ == "__main__":
    unittest.main()
