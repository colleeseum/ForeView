# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from decimal import Decimal
from pathlib import Path

import pytest

from localization.service import LocalizationService
from localization.value_formatter import ValueFormatter


@pytest.mark.parametrize("locale", ["en-CA", "fr-CA"])
def test_values_are_localized_without_changing_the_input(tmp_path, locale):
    service = LocalizationService(Path("localization"), tmp_path)
    formatter = ValueFormatter(service, locale)
    amount = Decimal("1234.50")
    if locale == "en-CA":
        assert formatter.money(amount) == "$1,234.50"
        assert formatter.percent("0.025") == "2.50%"
        assert formatter.date("2026-01-09") == "Jan 9, 2026"
    else:
        assert formatter.money(amount) == "1\u00a0234,50\u00a0$"
        assert formatter.percent("0.025") == "2,50\u00a0%"
        assert formatter.date("2026-01-09") == "9 janv. 2026"
    assert amount == Decimal("1234.50")
    assert formatter.money("1.005") == formatter.money("1.01")
    assert formatter.money("-1.005") == formatter.money("-1.01")
    assert formatter.number("1234.56789").endswith("56789")
    assert formatter.number("0", digits=2) == ("0.00" if locale == "en-CA" else "0,00")
    assert formatter.number("12", digits=0) == "12"
    assert formatter.number("1.005", digits=2) == formatter.number("1.01", digits=2)
    assert (
        formatter.money("9007199254740993.01")
        .replace("\u00a0", "")
        .replace(",", "")
        .startswith("$9007199254740993.01" if locale == "en-CA" else "900719925474099301$")
    )
    assert formatter.date("20260109") == formatter.date("2026-01-09")
    assert formatter.date("malformed source") == "malformed source"
    assert formatter.date(None) == ""
    assert formatter.date("") == ""
    assert formatter.percent("0.5", digits=0).startswith("50")
    for value in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ValueError):
            formatter.money(value)


def test_unknown_formatting_locale_uses_declared_fallback(tmp_path):
    service = LocalizationService(Path("localization"), tmp_path)
    assert ValueFormatter(service, "invalid-locale").money("1") == "$1.00"


def test_unusable_default_locale_reports_configuration_error(tmp_path):
    root = tmp_path / "catalogs"
    root.mkdir()
    (root / "registry.json").write_text(
        '{"locales": [{"code": "invalid-locale", "native_name": "Invalid"}]}',
        encoding="utf-8",
    )
    service = LocalizationService(root, tmp_path, default_locale="invalid-locale")
    with pytest.raises(ValueError, match="No supported formatting locale"):
        ValueFormatter(service, "invalid-locale")
