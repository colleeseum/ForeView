# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocaleDefinition:
    code: str
    native_name: str
    direction: str = "ltr"
    fallback: str | None = None


class LocalizationService:
    """Registry-backed localization with deterministic fallback and local persistence."""

    def __init__(self, root: Path, data_dir: Path, default_locale: str = "en-CA") -> None:
        self.root = root
        self.preference_path = data_dir / "locale.json"
        self.default_locale = default_locale
        self._locales = self._load_registry()
        self._catalog_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def _load_registry(self) -> dict[str, LocaleDefinition]:
        raw = json.loads((self.root / "registry.json").read_text(encoding="utf-8"))
        return {
            item["code"]: LocaleDefinition(
                code=item["code"],
                native_name=item["native_name"],
                direction=item.get("direction", "ltr"),
                fallback=item.get("fallback"),
            )
            for item in raw["locales"]
        }

    @property
    def locales(self) -> tuple[LocaleDefinition, ...]:
        return tuple(self._locales.values())

    def definition(self, code: str) -> LocaleDefinition:
        return self._locales.get(code, self._locales[self.default_locale])

    def selected_locale(self) -> str:
        try:
            value = json.loads(self.preference_path.read_text(encoding="utf-8")).get("locale")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            value = None
        return value if isinstance(value, str) and value in self._locales else self.default_locale

    def select(self, code: str) -> None:
        if code not in self._locales:
            raise ValueError(f"Unsupported locale: {code}")
        self.preference_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.preference_path.parent,
                prefix=f".{self.preference_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(json.dumps({"locale": code}, indent=2) + "\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.preference_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _catalog(self, code: str, namespace: str) -> dict[str, Any]:
        cache_key = (code, namespace)
        if cache_key in self._catalog_cache:
            return self._catalog_cache[cache_key]
        path = self.root / code / f"{namespace}.json"
        if not path.exists():
            catalog: dict[str, Any] = {}
        else:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                catalog = {}
            else:
                catalog = value if isinstance(value, dict) else {}
        self._catalog_cache[cache_key] = catalog
        return catalog

    @staticmethod
    def _lookup(catalog: dict[str, Any], key: str) -> str | None:
        value: Any = catalog
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value if isinstance(value, str) else None

    @staticmethod
    def _render(message: str, values: dict[str, object]) -> str | None:
        try:
            return message.format(**values)
        except (ValueError, LookupError, AttributeError, TypeError, OverflowError):
            return None

    def translate(self, code: str, key: str, **values: object) -> str:
        namespace, _, local_key = key.partition(".")
        if not local_key:
            return f"⟦{key}⟧"
        seen: set[str] = set()
        candidate: str | None = code
        while candidate and candidate not in seen:
            seen.add(candidate)
            message = self._lookup(self._catalog(candidate, namespace), local_key)
            if message is not None:
                rendered = self._render(message, values)
                if rendered is not None:
                    return rendered
            candidate = self.definition(candidate).fallback
        if self.default_locale not in seen:
            message = self._lookup(self._catalog(self.default_locale, namespace), local_key)
            if message is not None:
                rendered = self._render(message, values)
                if rendered is not None:
                    return rendered
        return f"⟦{key}⟧"
