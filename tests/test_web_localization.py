# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from pathlib import Path

from flask import Flask

from domain.validation_error import ValidationError
from domain.validation_lookup_error import ValidationLookupError
from localization import LocalizationService
from web.localization import error_data, localized_api_error, provider_presentation


def test_provider_presentation_falls_back_per_field_without_mutating_evidence(tmp_path):
    app = Flask(__name__)
    service = LocalizationService(Path(__file__).parents[1] / "localization", tmp_path)
    service.select("fr-CA")
    app.extensions["localization"] = service
    translations = {"fr-CA": {"display_name": "Importer", "help_text": " "}}
    with app.app_context():
        result = provider_presentation("Import", translations, help_text="Original instructions")
    assert result == {
        "display_name": "Importer",
        "help_text": "Original instructions",
        "field_languages": {"display_name": "fr-CA", "help_text": "en-CA"},
    }
    assert translations["fr-CA"]["help_text"] == " "


def test_typed_errors_preserve_embedding_contract_and_external_diagnostics(tmp_path):
    app = Flask(__name__)
    original = ValidationError("person_required", "Person is required")
    missing = ValidationLookupError("person_required", "Original diagnostic")
    with app.app_context():
        assert error_data(original) == {
            "error": "Person is required",
            "error_code": "person_required",
            "error_language": "en-CA",
        }
        service = LocalizationService(Path(__file__).parents[1] / "localization", tmp_path)
        service.select("fr-CA")
        app.extensions["localization"] = service
        assert error_data(original)["error_language"] == "fr-CA"
        assert error_data(missing)["error_language"] == "fr-CA"
        assert error_data(ValueError("External original diagnostic")) == {
            "error": "External original diagnostic",
            "error_language": "en-CA",
        }
        assert str(original) == "Person is required"


def test_api_error_has_stable_code_and_resolved_fallback_language(tmp_path):
    root = tmp_path / "catalogs"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {
                        "code": "ar-XB",
                        "native_name": "Synthetic",
                        "fallback": "en-CA",
                        "direction": "rtl",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    for code, messages in (
        ("en-CA", {"required": "A file is required"}),
        ("ar-XB", {"required": " "}),
    ):
        (root / code).mkdir()
        (root / code / "errors.json").write_text(json.dumps(messages), encoding="utf-8")
    service = LocalizationService(root, tmp_path / "runtime")
    service.select("ar-XB")
    app = Flask(__name__)
    app.extensions["localization"] = service
    with app.app_context():
        response, status = localized_api_error("required", 422)
        assert status == 422
        assert response.get_json() == {
            "error": "A file is required",
            "error_code": "required",
            "error_language": "en-CA",
        }
        missing, _ = localized_api_error("missing")
        assert missing.get_json()["error"] == "⟦errors.missing⟧"


def test_parameterized_error_falls_back_from_unrenderable_translation(tmp_path):
    root = tmp_path / "catalogs"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps(
            {
                "locales": [
                    {"code": "en-CA", "native_name": "English"},
                    {"code": "fr-CA", "native_name": "French", "fallback": "en-CA"},
                ]
            }
        ),
        encoding="utf-8",
    )
    for code, message in (("en-CA", "Unknown field: {field}"), ("fr-CA", "Champ : {missing}")):
        (root / code).mkdir()
        (root / code / "errors.json").write_text(json.dumps({"field": message}), encoding="utf-8")
    service = LocalizationService(root, tmp_path / "runtime")
    service.select("fr-CA")
    app = Flask(__name__)
    app.extensions["localization"] = service
    with app.app_context():
        response, _ = localized_api_error("field", field="Synthetic field")
        assert response.get_json()["error"] == "Unknown field: Synthetic field"
        assert response.get_json()["error_language"] == "en-CA"
