# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
import re
import shutil
from copy import deepcopy
from dataclasses import replace
from html import escape, unescape
from types import SimpleNamespace

import pytest

import app
import web.page_routes
import web.public_rule_routes
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from infrastructure.runtime_config import RuntimeConfig
from institution_support.institution_provider import InstitutionProvider
from localization import LocalizationService
from services.projections.public_rule_catalog import PublicRuleCatalog


@pytest.fixture
def application(tmp_path):
    runtime_dir = tmp_path / "runtime"
    create_synthetic_runtime(runtime_dir)
    runtime = RuntimeConfig.load(runtime_dir)
    app.initialize(runtime)
    application = app.create_app(runtime)
    root = tmp_path / "catalogs"
    shutil.copytree(app.ROOT / "localization", root)
    registry = json.loads((root / "registry.json").read_text())
    registry["locales"].append(
        {"code": "ar-XB", "native_name": "Synthetic RTL", "direction": "rtl", "fallback": "fr-CA"}
    )
    (root / "registry.json").write_text(json.dumps(registry))
    (root / "ar-XB").mkdir()
    application.extensions["localization"] = LocalizationService(root, runtime_dir)
    return application


def navigation(page):
    nav = re.search(r"<nav[^>]*public-rule-tabs[^>]*>(.*?)</nav>", page, re.S)
    assert nav
    return [
        (unescape(href), unescape(label).strip())
        for href, label in re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', nav.group(1), re.S)
    ]


@pytest.mark.parametrize("locale", ["en-CA", "fr-CA", "ar-XB"])
def test_jurisdiction_labels_preserve_codes_rules_hashes_and_financial_results(application, locale):
    client = application.test_client()
    before_links = navigation(client.get("/settings").text)
    packages = PublicRuleCatalog(app.ROOT / "public_rules").list_packages()
    before_rules = [(package.content_hash, package.rule_set.model_dump()) for package in packages]
    database = application.extensions["finance_runtime"].database_path
    before_database = database.read_bytes()
    before_projection = client.get("/api/salary-projection?start_year=2026&end_year=2027")
    assert before_projection.status_code == 200
    application.extensions["localization"].select(locale)
    response = client.get("/settings?jurisdiction=CA-QC&year=2026")
    assert response.status_code == 200
    links = navigation(response.text)
    assert [href for href, _ in links] == [href for href, _ in before_links]
    labels = [label for _, label in links]
    if locale == "en-CA":
        assert labels == [label for _, label in before_links]
        assert "Federal" in labels and "British Columbia" in labels and "Quebec" in labels
    else:
        assert labels == [
            "Fédéral",
            "Alberta",
            "Colombie-Britannique",
            "Manitoba",
            "Nouveau-Brunswick",
            "Terre-Neuve-et-Labrador",
            "Territoires du Nord-Ouest",
            "Nouvelle-Écosse",
            "Nunavut",
            "Ontario",
            "Île-du-Prince-Édouard",
            "Québec",
            "Saskatchewan",
            "Yukon",
        ]
    assert 'name="jurisdiction" value="CA-QC"' in response.text
    assert 'value="2026" selected' in response.text
    assert "ca-qc-2026-official" in response.text
    assert [
        (package.content_hash, package.rule_set.model_dump())
        for package in PublicRuleCatalog(app.ROOT / "public_rules").list_packages()
    ] == before_rules
    assert database.read_bytes() == before_database
    assert (
        client.get("/api/salary-projection?start_year=2026&end_year=2027").json
        == before_projection.json
    )
    assert "⟦" not in response.text


@pytest.mark.parametrize("locale", ["en-CA", "fr-CA", "ar-XB"])
def test_about_institutions_resolve_partial_and_empty_translations_without_changing_identity(
    application, monkeypatch, locale
):
    providers = (
        InstitutionProvider(
            "translated",
            "Synthetic Bank",
            translations={"fr-CA": {"display_name": "Banque fictive"}},
        ),
        InstitutionProvider(
            "partial", "Original Brand", translations={"fr-CA": {"help_text": "Aide"}}
        ),
        InstitutionProvider(
            "blank",
            "Brand <North>",
            translations={"fr-CA": {"display_name": " "}, "en-CA": {"display_name": ""}},
        ),
        InstitutionProvider(
            "english",
            "Source Identity",
            translations={
                "fr-CA": {"display_name": ""},
                "en-CA": {"display_name": "English display"},
            },
        ),
    )
    original = deepcopy(providers)
    monkeypatch.setattr(
        web.page_routes, "institution_registry", lambda: SimpleNamespace(providers=providers)
    )
    application.extensions["localization"].select(locale)
    response = application.test_client().get("/about")
    assert response.status_code == 200
    translated = "Synthetic Bank" if locale == "en-CA" else "Banque fictive"
    language = "en-CA" if locale == "en-CA" else "fr-CA"
    expected = [
        (translated, language),
        ("Original Brand", "en-CA"),
        ("Brand <North>", "en-CA"),
        ("English display", "en-CA"),
    ]
    for provider, (label, language) in zip(providers, expected, strict=True):
        assert (
            f'<td lang="{language}">{escape(label)}</td><td>{provider.key}</td><td>{provider.version}</td>'
            in response.text
        )
    assert providers == original
    assert "⟦" not in response.text


def test_unknown_jurisdiction_retains_its_code_instead_of_missing_message(application, monkeypatch):
    package = PublicRuleCatalog(app.ROOT / "public_rules").list_packages()[0]
    unknown = replace(
        package, rule_set=package.rule_set.model_copy(update={"jurisdiction": "CA-ZZ"})
    )
    monkeypatch.setattr(
        web.public_rule_routes,
        "_catalog",
        lambda: SimpleNamespace(list_packages=lambda: (unknown,)),
    )
    response = application.test_client().get("/settings")
    assert response.status_code == 200
    assert navigation(response.text) == [("/settings?jurisdiction=CA-ZZ", "CA-ZZ")]
    assert "⟦" not in response.text
