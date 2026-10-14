# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Localized help and independent provider fallback contract."""

from __future__ import annotations

import json
from dataclasses import fields as dataclass_fields
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from expense_sources.expense_source_provider import ExpenseSourceProvider
from income_sources.income_source_provider import IncomeSourceProvider
from institution_support.help_topic import HelpTopic
from institution_support.institution_provider import InstitutionProvider
from localization import LocalizationService
from localization.provider_content import localized_fields
from public_pension_sources.public_pension_source_provider import PublicPensionSourceProvider
from tax_notices.tax_notice_provider import TaxNoticeProvider
from web.help_routes import blueprint


def _service(tmp_path: Path) -> LocalizationService:
    root = Path(__file__).resolve().parents[1] / "localization"
    return LocalizationService(root, tmp_path)


def test_provider_fallback_per_field(tmp_path):
    service = _service(tmp_path)
    fields, languages = localized_fields(
        {"title": "English title", "body": "English body"},
        {"fr-CA": {"title": "Titre français"}},
        "fr-CA",
        service,
    )
    assert fields == {"title": "Titre français", "body": "English body"}
    assert languages == {"title": "fr-CA", "body": "en-CA"}


def test_provider_additional_locale_uses_registry_without_core_changes(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                    {"code": "es-MX", "native_name": "Español", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    service = LocalizationService(root, tmp_path)
    fields, languages = localized_fields(
        {"title": "Import", "body": "Instructions"},
        {"es-MX": {"title": "Importar"}},
        "es-MX",
        service,
    )
    assert fields == {"title": "Importar", "body": "Instructions"}
    assert languages["body"] == "en-CA"


def test_help_catalog_localized_in_french(tmp_path):
    service = _service(tmp_path)
    service.select("fr-CA")
    app = Flask(__name__)
    app.extensions["localization"] = service
    app.register_blueprint(blueprint)
    with app.test_client() as client:
        response = client.get("/api/help")
        assert response.status_code == 200
        data = response.get_json()
    assert data["language"] == "fr-CA"
    assert (
        next(category for category in data["categories"] if category["key"] == "financial")["title"]
        == "Dossiers financiers"
    )
    assert (
        next(article for article in data["articles"] if article["key"] == "expenses")["title"]
        == "Dépenses"
    )
    assert (
        next(tooltip for tooltip in data["tooltips"] if tooltip["key"] == "salary-rate")["title"]
        == "Taux salarial"
    )
    provider = next(
        article
        for article in data["articles"]
        if article["key"] == "institution-questrade-connection"
    )
    assert provider["title"] == "Connexion Questrade"
    assert provider["field_languages"]["body"] == "fr-CA"


@pytest.mark.parametrize(
    "provider, names",
    [
        (
            InstitutionProvider,
            "key display_name version aliases importers connection help_topics holds_securities statement_sources csv_parser balance_excluded_sources balance_including_snapshot_sources transaction_repair",
        ),
        (IncomeSourceProvider, "key display_name parser source_label help_text version detects"),
        (ExpenseSourceProvider, "key display_name parser detects help_text version"),
        (TaxNoticeProvider, "key display_name source_label parser detects help_text version"),
        (PublicPensionSourceProvider, "key display_name parser detects help_text version"),
        (HelpTopic, "key title body category parent_topic order owning_page"),
    ],
)
def test_provider_positional_constructors_remain_compatible(provider, names):
    expected = names.split()
    assert [field.name for field in dataclass_fields(provider)] == [*expected, "translations"]
    arguments = [object() for _ in expected]
    instance = provider(*arguments)
    for name, argument in zip(expected, arguments, strict=True):
        assert getattr(instance, name) is argument
    assert instance.translations == {}


def test_core_help_uses_declared_fallback_per_field_and_marks_actual_languages(tmp_path):
    root = tmp_path / "catalogs"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                    {"code": "es-MX", "native_name": "Español", "fallback": "fr-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    for locale, catalog in {
        "fr-CA": {
            "categories": {"financial": "Dossiers financiers"},
            "articles": {"expenses": {"title": "Dépenses", "body": "Instructions françaises"}},
            "tooltips": {"salary-rate": {"title": "Taux salarial", "body": None}},
            "provider_templates": {"institution_summary": "Aide du module {name}."},
        },
        "es-MX": {"articles": {"expenses": {"title": "Gastos", "body": " "}}},
    }.items():
        directory = root / locale
        directory.mkdir()
        (directory / "help.json").write_text(json.dumps(catalog), encoding="utf-8")
    service = LocalizationService(root, tmp_path)
    service.select("es-MX")
    app = Flask(__name__)
    app.extensions["localization"] = service
    app.register_blueprint(blueprint)
    data = app.test_client().get("/api/help").get_json()
    category = next(item for item in data["categories"] if item["key"] == "financial")
    assert (category["title"], category["language"]) == ("Dossiers financiers", "fr-CA")
    article = next(item for item in data["articles"] if item["key"] == "expenses")
    assert article["title"] == "Gastos"
    assert article["body"] == "Instructions françaises"
    assert article["field_languages"] == {"title": "es-MX", "summary": "en-CA", "body": "fr-CA"}
    tooltip = next(item for item in data["tooltips"] if item["key"] == "salary-rate")
    assert tooltip["field_languages"] == {"title": "fr-CA", "body": "en-CA"}
    provider = next(item for item in data["articles"] if item["key"] == "institution-rbc-imports")
    assert provider["field_languages"] == {"title": "fr-CA", "summary": "fr-CA", "body": "fr-CA"}
    assert provider["summary"] == "Aide du module RBC."


def test_french_seasonal_guidance_retains_stream_and_availability_constraints(tmp_path):
    service = _service(tmp_path)
    body = service.catalog("fr-CA", "help")["articles"]["expense-seasonal-estimate"]["body"]
    assert "même flux de dépenses" in body
    assert "toute l’année civile" in body
    assert "chevauchements ne sont pas résolus" in body


@pytest.mark.parametrize(
    "key, fragment",
    [
        ("income-source-ufile", "Taxpayer’s copy"),
        ("tax-notice-cra-noa", "numéro d’assurance sociale"),
        ("tax-notice-revenu-quebec-noa", "RQAP"),
        ("public-pension-retraite-quebec-participation", "incomplètes"),
        ("expense-source-hydro-quebec", "versements égaux"),
    ],
)
def test_provider_help_text_translations_reach_full_help(tmp_path, key, fragment):
    service = _service(tmp_path)
    service.select("fr-CA")
    app = Flask(__name__)
    app.extensions["localization"] = service
    app.register_blueprint(blueprint)
    article = next(
        item
        for item in app.test_client().get("/api/help").get_json()["articles"]
        if item["key"] == key
    )
    assert article["field_languages"]["body"] == "fr-CA"
    assert fragment in article["body"]


@pytest.mark.parametrize(
    "translation, expected, language",
    [
        ({"display_name": "Source synthétique"}, "Original provider instructions", "en-CA"),
        ({"help_text": "Instructions françaises"}, "Instructions françaises", "fr-CA"),
        (
            {"help_text": "Instructions françaises", "body": "Explicit override"},
            "Explicit override",
            "fr-CA",
        ),
    ],
)
def test_provider_help_alias_and_fallback_preserve_original_source(
    tmp_path, monkeypatch, translation, expected, language
):
    from income_sources import income_source_registry

    original = replace(
        income_source_registry.providers[0],
        help_text="Original provider instructions",
        translations={"fr-CA": translation},
    )
    monkeypatch.setattr(
        "web.help_routes.income_source_registry", SimpleNamespace(providers=(original,))
    )
    service = _service(tmp_path)
    service.select("fr-CA")
    app = Flask(__name__)
    app.extensions["localization"] = service
    app.register_blueprint(blueprint)
    article = next(
        item
        for item in app.test_client().get("/api/help").get_json()["articles"]
        if item["key"] == "income-source-ufile"
    )
    assert article["body"] == expected
    assert article["field_languages"]["body"] == language
    assert original.help_text == "Original provider instructions"


@pytest.mark.parametrize(
    "key, required_guidance",
    [
        (
            "factual-corrections",
            (
                "valeur sous-jacente ou sa source",
                "Confirmez-la seulement après avoir comparé la source actuelle",
                "Réimportez plutôt le document",
                "source conservée elle-même est incomplète ou périmée",
            ),
        ),
        (
            "public-rule-approval",
            (
                "ne certifie ni l’exhaustivité ni l’exactitude",
                "sources officielles",
                "concepts fiscaux, calculs, crédits, cotisations, seuils",
                "réductions progressives, surtaxes et mécanismes d’indexation",
                "ajoutés, supprimés ou modifiés",
                "code de l’importateur",
            ),
        ),
    ],
)
def test_french_help_api_preserves_safety_guidance(tmp_path, key, required_guidance):
    service = _service(tmp_path)
    service.select("fr-CA")
    app = Flask(__name__)
    app.extensions["localization"] = service
    app.register_blueprint(blueprint)
    with app.test_client() as client:
        response = client.get("/api/help")
    assert response.status_code == 200
    article = next(item for item in response.get_json()["articles"] if item["key"] == key)
    assert article["field_languages"]["body"] == "fr-CA"
    for guidance in required_guidance:
        assert guidance in article["body"]
