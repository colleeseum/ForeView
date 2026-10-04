# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import app as application
from infrastructure.runtime_config import RuntimeConfig
from synthetic_runtime import create_synthetic_runtime


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def _runtime(self, name: str, values: dict[str, object]) -> Path:
        folder = self.root / name
        folder.mkdir()
        (folder / "finance.config.json").write_text(json.dumps(values))
        return folder

    def test_load_keeps_non_empty_values_and_derives_paths(self):
        folder = self._runtime("one", {"TLS_CERT_FILE": "cert.pem", "EMPTY": "", "NONE": None})

        runtime = RuntimeConfig.load(folder)

        self.assertEqual(runtime.data_dir, folder.resolve())
        self.assertEqual(runtime.database_path, folder.resolve() / "finance.sqlite3")
        self.assertEqual(runtime.config_path, folder.resolve() / "finance.config.json")
        self.assertEqual(dict(runtime.values), {"TLS_CERT_FILE": "cert.pem"})

    def test_missing_config_file_gives_an_empty_runtime(self):
        runtime = RuntimeConfig.load(self.root / "absent")

        self.assertEqual(dict(runtime.values), {})
        self.assertIsNone(runtime.setting("ANYTHING"))

    def test_runtime_is_immutable_and_with_values_returns_a_copy(self):
        runtime = RuntimeConfig(self.root, {"KEEP": "yes", "DROP": "gone"})

        changed = runtime.with_values(ADDED="new", DROP=None)

        self.assertEqual(dict(changed.values), {"KEEP": "yes", "ADDED": "new"})
        self.assertEqual(dict(runtime.values), {"KEEP": "yes", "DROP": "gone"})
        with self.assertRaises(FrozenInstanceError):
            runtime.data_dir = self.root  # type: ignore[misc]
        with self.assertRaises(TypeError):
            runtime.values["KEEP"] = "no"  # type: ignore[index]

    def test_environment_overrides_config_and_only_strings_are_settings(self):
        runtime = RuntimeConfig(self.root, {"NAME": "from-config", "LIST": ["a"]})

        with patch.dict("os.environ", {"NAME": "from-env"}):
            self.assertEqual(runtime.setting("NAME"), "from-env")
        self.assertEqual(runtime.setting("NAME"), "from-config")
        self.assertIsNone(runtime.setting("LIST"))
        self.assertEqual(runtime.setting("MISSING", "fallback"), "fallback")

    def test_ssl_context_requires_both_files(self):
        self.assertIsNone(RuntimeConfig(self.root, {"TLS_CERT_FILE": "cert.pem"}).ssl_context())
        self.assertEqual(
            RuntimeConfig(
                self.root, {"TLS_CERT_FILE": "cert.pem", "TLS_KEY_FILE": "key.pem"}
            ).ssl_context(),
            ("cert.pem", "key.pem"),
        )

    def test_context_exposes_the_runtime_to_institutions(self):
        runtime = RuntimeConfig(self.root / "db", {"NAME": "value"})

        context = runtime.context()

        self.assertEqual(context.setting("NAME"), "value")
        self.assertEqual(dict(context.config), {"NAME": "value"})
        with context.connect() as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertTrue(runtime.database_path.exists())

    def test_two_apps_in_one_process_serve_their_own_runtime(self):
        first_folder, _ = create_synthetic_runtime(self.root / "first")
        second_folder = self._runtime("second", {"RUNTIME_ENVIRONMENT": "synthetic"})
        first = RuntimeConfig.load(first_folder.parent)
        second = RuntimeConfig.load(second_folder)
        application.initialize(first)
        application.initialize(second)

        first_accounts = (
            application.create_app(first).test_client().get("/api/model/accounts").get_json()
        )
        second_accounts = (
            application.create_app(second).test_client().get("/api/model/accounts").get_json()
        )

        self.assertTrue(first_accounts["accounts"])
        self.assertEqual(second_accounts["accounts"], [])

    def test_runtime_connections_enforce_declared_foreign_keys(self):
        runtime = RuntimeConfig(self.root / "foreign-keys")
        application.initialize(runtime)

        with runtime.connect() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO account_owners(account_id, person_id) VALUES (999, 999)"
                )


if __name__ == "__main__":
    unittest.main()
