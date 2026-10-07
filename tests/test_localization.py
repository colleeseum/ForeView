# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from datetime import date
from types import SimpleNamespace

import pytest

from localization import LocalizationService


def write_locale(root, code, messages):
    folder = root / code
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "core.json").write_text(json.dumps(messages), encoding="utf-8")


def test_registry_supports_third_locale_without_feature_branches(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {
                        "code": "xx-TEST",
                        "native_name": "Test",
                        "direction": "rtl",
                        "fallback": "en-CA",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"hello": "Hello", "fallback": "Fallback"})
    write_locale(root, "xx-TEST", {"hello": "Test hello"})
    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("xx-TEST", "core.hello") == "Test hello"
    assert service.translate("xx-TEST", "core.fallback") == "Fallback"
    assert service.definition("xx-TEST").direction == "rtl"


def test_selection_persists_and_missing_key_is_visible(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"hello": "Hello"})
    write_locale(root, "fr-CA", {"hello": "Bonjour"})
    data_dir = tmp_path / "runtime"
    service = LocalizationService(root, data_dir)

    service.select("fr-CA")

    restarted = LocalizationService(root, data_dir)
    assert restarted.selected_locale() == "fr-CA"
    assert restarted.translate("fr-CA", "core.hello") == "Bonjour"
    assert restarted.translate("fr-CA", "core.missing") == "⟦core.missing⟧"


def test_failed_locale_replacement_preserves_previous_preference(tmp_path, monkeypatch):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"hello": "Hello"})
    write_locale(root, "fr-CA", {"hello": "Bonjour"})
    data_dir = tmp_path / "runtime"
    service = LocalizationService(root, data_dir)
    service.select("en-CA")

    def fail_replace(source, destination):
        raise OSError("synthetic replacement failure")

    monkeypatch.setattr("localization.service.os.replace", fail_replace)

    with pytest.raises(OSError, match="synthetic replacement failure"):
        service.select("fr-CA")

    assert json.loads(service.preference_path.read_text(encoding="utf-8")) == {"locale": "en-CA"}
    assert list(data_dir.glob(".locale.json.*.tmp")) == []


def test_malformed_catalog_uses_fallback(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"hello": "Hello"})
    folder = root / "fr-CA"
    folder.mkdir()
    (folder / "core.json").write_text("{not-json", encoding="utf-8")

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("fr-CA", "core.hello") == "Hello"


def test_default_fallback_missing_placeholder_is_visible(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "xx-TEST", "native_name": "Test"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"greeting": "Hello {name}"})
    write_locale(root, "xx-TEST", {})

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("xx-TEST", "core.greeting") == "⟦core.greeting⟧"


def test_non_utf8_catalog_uses_fallback(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"hello": "Hello"})
    folder = root / "fr-CA"
    folder.mkdir()
    (folder / "core.json").write_bytes(b"\\xff")

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("fr-CA", "core.hello") == "Hello"


def test_malformed_format_string_is_visible_instead_of_raising(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps({"locales": [{"code": "en-CA", "native_name": "English"}]}),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"broken": "Hello {name"})

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("en-CA", "core.broken", name="Ada") == "⟦core.broken⟧"


def test_malformed_persisted_locale_falls_back_to_default(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps({"locales": [{"code": "en-CA", "native_name": "English"}]}),
        encoding="utf-8",
    )
    data_dir = tmp_path / "runtime"
    data_dir.mkdir()
    (data_dir / "locale.json").write_text(json.dumps({"locale": []}), encoding="utf-8")

    service = LocalizationService(root, data_dir)
    assert service.selected_locale() == "en-CA"

    (data_dir / "locale.json").write_bytes(b"\\xff")
    assert service.selected_locale() == "en-CA"


def test_unrenderable_translation_continues_to_registered_fallback(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"greeting": "Hello {name}"})
    write_locale(root, "fr-CA", {"greeting": "Bonjour {name"})

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("fr-CA", "core.greeting", name="Ada") == "Hello Ada"


def test_incompatible_format_value_continues_to_registered_fallback(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"amount": "Amount {amount}"})
    write_locale(root, "fr-CA", {"amount": "Montant {amount:,.2f}"})

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("fr-CA", "core.amount", amount=None) == "Amount None"


def test_overflowing_format_value_continues_to_registered_fallback(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"amount": "Amount {amount}"})
    write_locale(root, "fr-CA", {"amount": "Montant {amount:c}"})

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("fr-CA", "core.amount", amount=-1) == "Amount -1"


def test_missing_format_attribute_continues_to_registered_fallback(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "Français", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"value": "Value {value}"})
    write_locale(root, "fr-CA", {"value": "{value:{width.missing}}"})

    service = LocalizationService(root, tmp_path / "runtime")

    assert service.translate("fr-CA", "core.value", value=12, width=object()) == "Value 12"


def test_compound_format_fields_render_from_supplied_root_values(tmp_path):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps({"locales": [{"code": "en-CA", "native_name": "English"}]}),
        encoding="utf-8",
    )
    write_locale(
        root,
        "en-CA",
        {
            "attribute": "Hello {person.name}",
            "item": "Hello {person[name]}",
        },
    )

    service = LocalizationService(root, tmp_path / "runtime")

    assert (
        service.translate("en-CA", "core.attribute", person=SimpleNamespace(name="Ada"))
        == "Hello Ada"
    )
    assert service.translate("en-CA", "core.item", person={"name": "Ada"}) == "Hello Ada"


def test_catalog_is_loaded_once_per_locale_and_namespace(tmp_path, monkeypatch):
    root = tmp_path / "localization"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps({"locales": [{"code": "en-CA", "native_name": "English"}]}),
        encoding="utf-8",
    )
    write_locale(root, "en-CA", {"hello": "Hello", "goodbye": "Goodbye"})
    service = LocalizationService(root, tmp_path / "runtime")
    catalog_path = root / "en-CA" / "core.json"
    path_type = type(catalog_path)
    original_read_text = path_type.read_text
    reads = 0

    def count_reads(path, *args, **kwargs):
        nonlocal reads
        if path == catalog_path:
            reads += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(path_type, "read_text", count_reads)

    assert service.translate("en-CA", "core.hello") == "Hello"
    assert service.translate("en-CA", "core.goodbye") == "Goodbye"
    assert reads == 1


def test_unsupported_locale_submission_returns_bad_request(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    runtime = RuntimeConfig(tmp_path / "runtime")
    flask_app = application.create_app(runtime)
    flask_app.config.update(TESTING=True)
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf-token"

    response = client.post(
        "/application-settings/language",
        data={"csrf_token": "test-csrf-token", "locale": "not-supported"},
    )

    assert response.status_code == 400


def test_locale_submission_ignores_external_redirect_target(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    runtime = RuntimeConfig(tmp_path / "runtime")
    flask_app = application.create_app(runtime)
    flask_app.config.update(TESTING=True)
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf-token"

    response = client.post(
        "/application-settings/language",
        data={
            "csrf_token": "test-csrf-token",
            "locale": "fr-CA",
            "next": "https://example.invalid/phish",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/application-settings"
    assert json.loads((runtime.data_dir / "locale.json").read_text(encoding="utf-8")) == {
        "locale": "fr-CA"
    }


def test_dashboard_server_rendered_text_is_localized(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    runtime = RuntimeConfig(tmp_path / "runtime")
    flask_app = application.create_app(runtime)
    flask_app.config.update(TESTING=True)
    localization = flask_app.extensions["localization"]
    localization.select("fr-CA")

    response = flask_app.test_client().get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<html lang="fr-CA" dir="ltr">' in page
    assert "Par catégorie de compte" in page
    assert "Détail des liquidités" in page
    assert "Recent transactions" not in page


def test_locale_options_declare_their_own_language_and_direction(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    runtime = RuntimeConfig(tmp_path / "runtime")
    flask_app = application.create_app(runtime)
    flask_app.config.update(TESTING=True)

    response = flask_app.test_client().get("/application-settings")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<option value="en-CA" lang="en-CA" dir="ltr" selected>English</option>' in page
    assert '<option value="fr-CA" lang="fr-CA" dir="ltr">Français</option>' in page


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/setup", "Configurer le modèle"),
        ("/accounts", "Comptes regroupés selon les règles financières"),
        ("/income", "Revenus et données fiscales"),
        ("/connections", "Institutions liées"),
        ("/transactions", "Historique des flux de trésorerie"),
        ("/salary-projection", "Emploi et revenu disponible"),
        ("/about", "À propos de ForeView"),
    ],
)
def test_representative_server_pages_render_in_french(tmp_path, path, expected):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    runtime = RuntimeConfig(tmp_path / "runtime")
    flask_app = application.create_app(runtime)
    flask_app.config.update(TESTING=True)
    flask_app.extensions["localization"].select("fr-CA")

    response = flask_app.test_client().get(path)
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<html lang="fr-CA" dir="ltr">' in page
    assert expected in page


def test_tax_rules_template_compiles_and_localized_labels_exist(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    flask_app = application.create_app(RuntimeConfig(tmp_path / "runtime"))
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        flask_app.jinja_env.get_template("public_rules.html")
        service = flask_app.extensions["localization"]
        assert (
            service.translate("fr-CA", "pages_server.assets.principal_residence")
            == "Résidence principale"
        )
        assert service.translate("fr-CA", "pages_server.assets.property_type_examples").startswith(
            "Résidence principale"
        )
        assert service.translate("fr-CA", "pages_server.expenses.person") == "Personne"
        assert service.translate("fr-CA", "pages_server.expenses.property") == "Propriété"


def test_dashboard_js_owned_regions_keep_english_language_metadata(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    flask_app = application.create_app(RuntimeConfig(tmp_path / "runtime"))
    flask_app.config.update(TESTING=True)
    flask_app.extensions["localization"].select("fr-CA")
    response = flask_app.test_client().get("/")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    for element_id in (
        "dashboard-metrics",
        "dashboard-categories",
        "dashboard-liquidity",
        "dashboard-maturities",
        "dashboard-transactions",
    ):
        assert f'id="{element_id}" lang="en-CA"' in page


def test_french_expense_association_selector_is_localized(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig
    from services.expense_service import ExpenseService
    from tests.support import create_person

    runtime = RuntimeConfig(tmp_path / "runtime")
    flask_app = application.create_app(runtime)
    flask_app.config.update(TESTING=True)
    application.initialize(runtime)
    with runtime.connect() as connection:
        person_id = create_person(connection, "Synthetic Person")
        service = ExpenseService(connection)
        category = service.create_category("Utilities", "required")
        service.create_manual(
            name="Electricity",
            category_id=category.id,
            amount="125.50",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            association_kind="person",
            association_id=person_id,
            period_kind="recurring_statement",
        )
    flask_app.extensions["localization"].select("fr-CA")
    response = flask_app.test_client().get("/expenses")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Personne: Synthetic Person" in page
    assert "Utilities · Obligatoire" in page
    assert "2026-01-01 au 2026-01-31" in page
    assert "Période de relevé récurrente" in page
    assert f"Personne #{person_id}" in page
    assert "Manuelle" in page
    assert "Aucun chevauchement" in page
    assert "Résidence principale" == flask_app.extensions["localization"].translate(
        "fr-CA", "pages_server.assets.principal_residence"
    )


def test_french_expense_form_status_is_localized(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig
    from repositories.expense_repository import ExpenseRepository

    runtime = RuntimeConfig(tmp_path / "runtime")
    flask_app = application.create_app(runtime)
    flask_app.config.update(TESTING=True)
    application.initialize(runtime)
    flask_app.extensions["localization"].select("fr-CA")
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf-token"

    response = client.post(
        "/expenses/categories",
        data={
            "csrf_token": "test-csrf-token",
            "year": "2026",
            "name": "Services publics",
            "classification": "required",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        '<p class="connection-notice" lang="fr-CA" role="status">Catégorie de dépenses créée.</p>'
    ) in response.get_data(as_text=True)

    with runtime.connect() as connection:
        category_id = ExpenseRepository(connection).list_categories()[0].id
    response = client.post(
        "/expenses/manual",
        data={
            "csrf_token": "test-csrf-token",
            "year": "2026",
            "name": "Électricité",
            "category_id": str(category_id),
            "amount": "125.50",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "association": "household",
            "period_kind": "recurring_statement",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert (
        '<p class="connection-notice" lang="fr-CA" role="status">Dépense factuelle enregistrée.</p>'
    ) in response.get_data(as_text=True)


def test_french_disclaimer_marks_canonical_english_title(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    flask_app = application.create_app(RuntimeConfig(tmp_path / "runtime"))
    flask_app.config.update(TESTING=True)
    flask_app.extensions["localization"].select("fr-CA")

    response = flask_app.test_client().get("/disclaimer")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<title lang="en-CA">Disclaimer</title>' in page
    assert '<h1 lang="en-CA">Disclaimer</h1>' in page
    assert '<article class="dashboard-panel legal-document" lang="en-CA"' in page


def test_reviewed_server_locale_boundaries_and_labels(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    flask_app = application.create_app(RuntimeConfig(tmp_path / "runtime"))
    flask_app.config.update(TESTING=True)
    flask_app.extensions["localization"].select("fr-CA")
    client = flask_app.test_client()
    connections = client.get("/connections").get_data(as_text=True)
    assets = client.get("/accounts").get_data(as_text=True)
    income = client.get("/income").get_data(as_text=True)
    assert 'data-default-text="Tout synchroniser"' in connections
    assert 'data-busy-text="Synchronisation..."' in connections
    assert 'id="connection-list" lang="en-CA"' in connections
    assert 'data-add-text="Ajouter un compte"' in assets
    assert 'data-edit-text="Modifier le compte"' in assets
    assert 'data-add-text="Ajouter un CPG"' in assets
    assert 'data-edit-text="Modifier le CPG"' in assets
    assert 'data-add-text="Ajouter un bien immobilier"' in assets
    assert 'data-edit-text="Modifier le bien immobilier"' in assets
    assert 'data-total-text="Propriété sélectionnée : {percentage} %"' in assets
    assert 'data-invalid-text="doit totaliser 100 %"' in assets
    assert "Colombie-Britannique" in income
    assert "Territoires du Nord-Ouest" in income
    assert "Revenu d’emploi moins la prime" in income
    assert "minus bonus" not in income
    assert "Autres revenus" in income
    assert "Déclaration T1 produite" in income
    assert "Saisie manuelle" in income
    assert "Other income" not in income
    service = flask_app.extensions["localization"]
    assert service.translate("fr-CA", "pages_server.expenses.unavailable") == "Indisponible"
    assert "inflation" in service.translate(
        "fr-CA", "pages_server.expenses.seasonal_note", rate="2,00"
    )


def test_js_owned_regions_and_status_messages_are_language_safe(tmp_path):
    import app as application
    from infrastructure.runtime_config import RuntimeConfig

    flask_app = application.create_app(RuntimeConfig(tmp_path / "runtime"))
    flask_app.config.update(TESTING=True)
    flask_app.extensions["localization"].select("fr-CA")
    client = flask_app.test_client()
    for path, element_ids in {
        "/income": ("income-summary", "income-history", "income-tax-returns"),
        "/transactions": ("transactions-table-content", "import-history-content"),
        "/accounts": ("accounts-table-content",),
        "/setup": ("people-list", "accounts-list"),
        "/salary-projection": ("salary-table", "salary-tabs"),
    }.items():
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        for element_id in element_ids:
            assert f'id="{element_id}" lang="en-CA"' in html

    transactions = client.get("/transactions").get_data(as_text=True)
    assert 'id="import-dialog-title"' in transactions
    assert "Importer des transactions" in transactions or "Importer" in transactions

    salary = client.get("/salary-projection").get_data(as_text=True)
    assert 'data-saved-text="' in salary
    assert 'data-dirty-text="' in salary
    assert "Changes are saved to the selected scenario." not in salary
