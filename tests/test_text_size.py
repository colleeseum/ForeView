# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json

import pytest

import app
from devtools.synthetic.synthetic_runtime import create_synthetic_runtime
from infrastructure.appearance_preferences import AppearancePreferences
from infrastructure.runtime_config import RuntimeConfig
from services.runtime.runtime_backup_service import RuntimeBackupService


@pytest.mark.parametrize("size", AppearancePreferences.text_sizes)
def test_preference_survives_restart_and_isolates_runtime(tmp_path, size):
    first = AppearancePreferences(tmp_path / "first")
    second = AppearancePreferences(tmp_path / "second")
    assert first.text_size() == second.text_size() == "small"
    first.select_text_size(size)
    assert AppearancePreferences(tmp_path / "first").text_size() == size
    assert second.text_size() == "small"
    before = first.path.read_bytes()
    with pytest.raises(ValueError):
        first.select_text_size("../small")
    assert first.path.read_bytes() == before


@pytest.mark.parametrize(
    "value", ["{", "null", "[]", '"small"', '{"text_size":[]}', '{"text_size":"tiny"}', "{}"]
)
def test_malformed_appearance_uses_small_without_rewriting(tmp_path, value):
    preference = AppearancePreferences(tmp_path)
    preference.path.write_text(value)
    assert preference.text_size() == "small"
    assert preference.path.read_text() == value


def test_non_utf8_appearance_and_failed_atomic_save_preserve_previous(tmp_path, monkeypatch):
    preference = AppearancePreferences(tmp_path)
    preference.path.write_bytes(b"\xff")
    assert preference.text_size() == "small"
    preference.select_text_size("normal")

    def fail_replace(*args):
        raise OSError("Synthetic private filesystem detail")

    monkeypatch.setattr("infrastructure.appearance_preferences.os.replace", fail_replace)
    with pytest.raises(OSError):
        preference.select_text_size("small")
    assert preference.text_size() == "normal"
    assert list(tmp_path.glob(".appearance.*.tmp")) == []


@pytest.mark.parametrize("locale", ["en-CA", "fr-CA"])
def test_csrf_validation_failures_and_saved_setting_feedback(tmp_path, monkeypatch, locale):
    runtime = RuntimeConfig(tmp_path)
    application = app.create_app(runtime)
    application.extensions["localization"].select(locale)
    client = application.test_client()
    endpoint = "/application-settings/text-size"
    assert client.post(endpoint, data={"text_size": "small"}).status_code == 403
    preference = application.extensions["appearance"]
    assert not preference.path.exists()
    with client.session_transaction() as session:
        session["csrf_token"] = "synthetic"
    invalid = client.post(endpoint, data={"csrf_token": "synthetic", "text_size": "tiny"})
    assert invalid.status_code == 400
    assert 'role="alert"' in invalid.text
    assert not preference.path.exists()
    response = client.post(endpoint, data={"csrf_token": "synthetic", "text_size": "normal"})
    assert response.status_code == 303
    assert response.location == "/application-settings"
    page = client.get(response.location).text
    assert 'data-text-size="normal"' in page
    assert 'value="normal" selected' in page
    assert 'role="status"' in page
    assert "⟦" not in page
    assert application.extensions["localization"].selected_locale() == locale

    def fail_save(value):
        raise OSError("Synthetic private filesystem detail")

    monkeypatch.setattr(preference, "select_text_size", fail_save)
    failed = client.post(endpoint, data={"csrf_token": "synthetic", "text_size": "small"})
    assert failed.status_code == 503
    assert 'data-text-size="normal"' in failed.text
    assert 'value="small" selected' in failed.text
    assert 'role="alert"' in failed.text
    assert "Synthetic private filesystem detail" not in failed.text
    assert preference.text_size() == "normal"


def test_all_pages_restore_size_after_app_restart_without_changing_financial_data(tmp_path):
    create_synthetic_runtime(tmp_path)
    runtime = RuntimeConfig.load(tmp_path)
    application = app.create_app(runtime)
    app.initialize(runtime)
    client = application.test_client()
    paths = [
        "/",
        "/accounts",
        "/transactions",
        "/income",
        "/expenses",
        "/salary-projection",
        "/setup",
        "/connections",
        "/settings",
        "/application-settings",
        "/about",
        "/disclaimer",
    ]
    api_paths = [
        "/api/dashboard",
        "/api/model/accounts",
        "/api/model/transactions?account_type=non_registered",
        "/api/salary-projection?start_year=2026&end_year=2027",
    ]
    before = [client.get(path).json for path in api_paths]
    application.extensions["appearance"].select_text_size("large")
    restarted = app.create_app(runtime)
    restarted_client = restarted.test_client()
    for path in paths:
        response = restarted_client.get(path)
        assert response.status_code == 200, path
        assert 'data-text-size="large"' in response.text
    assert [restarted_client.get(path).json for path in api_paths] == before
    assert json.loads((tmp_path / "appearance.json").read_text()) == {"text_size": "large"}


def test_backup_round_trip_and_checksum_protect_appearance(tmp_path):
    runtime = RuntimeConfig(tmp_path / "runtime")
    app.initialize(runtime)
    preference = AppearancePreferences(runtime.data_dir)
    preference.select_text_size("normal")
    service = RuntimeBackupService()
    backup = service.create(runtime, tmp_path / "backup")
    preference.select_text_size("small")
    safety = service.restore(backup, runtime, replace=True)
    assert preference.text_size() == "normal"
    assert AppearancePreferences(safety).text_size() == "small"
    (backup / "appearance.json").write_text('{"text_size":"large"}')
    with pytest.raises(RuntimeError, match="checksum failed: appearance.json"):
        service.restore(backup, runtime, replace=True)
    assert preference.text_size() == "normal"


def test_restore_older_backup_without_appearance_returns_to_small(tmp_path):
    runtime = RuntimeConfig(tmp_path / "runtime")
    app.initialize(runtime)
    service = RuntimeBackupService()
    backup = service.create(runtime, tmp_path / "old-backup")
    preference = AppearancePreferences(runtime.data_dir)
    preference.select_text_size("large")
    service.restore(backup, runtime, replace=True)
    assert preference.text_size() == "small"
    assert not preference.path.exists()
