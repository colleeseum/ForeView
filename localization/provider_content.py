# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Provider-owned display translations; never translate source evidence."""

from __future__ import annotations

from collections.abc import Mapping

from localization.service import LocalizationService


def localized_fields(
    fields: Mapping[str, str],
    translations: Mapping[str, Mapping[str, str]] | None,
    locale: str,
    localization: LocalizationService,
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve each UI field through the application's declared fallback chain.

    A provider may supply any registered locale; incomplete catalogs fall back
    per field. Returns the resolved fields and a language marker for accessibility.
    Source text, document identifiers and provenance must not pass through here.
    """
    translations = translations or {}
    result: dict[str, str] = {}
    languages: dict[str, str] = {}
    for key, original in fields.items():
        for candidate in localization.fallback_chain(locale):
            catalog = translations.get(candidate, {})
            translated = catalog.get(key) if isinstance(catalog, Mapping) else None
            if isinstance(translated, str) and translated.strip():
                result[key] = translated
                languages[key] = candidate
                break
        else:
            result[key] = original
            languages[key] = localization.default_locale
    return result, languages
