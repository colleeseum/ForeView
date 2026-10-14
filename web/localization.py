# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""HTTP presentation adapters. Source evidence and external diagnostics bypass these helpers."""

from collections.abc import Mapping

from flask import current_app, jsonify

from domain.validation_error import ValidationError
from domain.validation_lookup_error import ValidationLookupError
from localization import LocalizationService
from localization.provider_content import localized_fields


def provider_presentation(
    display_name: str,
    translations: Mapping[str, Mapping[str, str]],
    **additional_fields: str,
) -> dict[str, object]:
    localization: LocalizationService = current_app.extensions["localization"]
    fields, languages = localized_fields(
        {"display_name": display_name, **additional_fields},
        translations,
        localization.selected_locale(),
        localization,
    )
    return {**fields, "field_languages": languages}


def localized_api_error(key: str, status: int = 400, /, **values: object):
    """A stable error code with a localized message and its resolved language."""
    return jsonify(localized_error_data(key, **values)), status


def error_data(error: Exception) -> dict[str, str]:
    """Translate known validation identities; leave uncoded diagnostics untouched.

    Independently mounted blueprints without a localization service retain default
    diagnostics, matching their pre-localization embedding contract.
    """
    if isinstance(error, (ValidationError, ValidationLookupError)):
        if "localization" in current_app.extensions:
            return localized_error_data(error.code, **error.values)
        return {"error": str(error), "error_code": error.code, "error_language": "en-CA"}
    return {"error": str(error), "error_language": "en-CA"}


def localized_error_data(key: str, /, **values: object) -> dict[str, str]:
    """Shared error presentation for JSON responses and server-rendered forms."""
    localization: LocalizationService = current_app.extensions["localization"]
    locale = localization.selected_locale()
    translations: dict[str, dict[str, str]] = {}
    for code in localization.fallback_chain(locale):
        message = localization.catalog(code, "errors").get(key)
        if isinstance(message, str):
            try:
                translations[code] = {"error": message.format(**values)}
            except (ValueError, LookupError, AttributeError, TypeError, OverflowError):
                continue
    fields, languages = localized_fields(
        {"error": localization.translate(localization.default_locale, f"errors.{key}", **values)},
        translations,
        locale,
        localization,
    )
    return {**fields, "error_code": key, "error_language": languages["error"]}
