# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
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


def test_untranslated_dashboard_region_is_marked_as_english(tmp_path):
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
    assert '<div class="page-content" lang="en-CA" dir="ltr">' in page
    assert '<p class="empty-panel" lang="fr-CA" dir="ltr">' in page


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
