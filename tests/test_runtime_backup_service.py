# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import app as application
from infrastructure.runtime_config import RuntimeConfig
from services.runtime_backup_service import RuntimeBackupService


class RuntimeBackupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.runtime = RuntimeConfig(self.root / "runtime")
        self.runtime.data_dir.mkdir()
        self.runtime.config_path.write_text(json.dumps({"RUNTIME_ENVIRONMENT": "synthetic"}))
        application.initialize(self.runtime)
        with self.runtime.connect() as connection:
            connection.execute("INSERT INTO people(name) VALUES ('Original Person')")
        self.service = RuntimeBackupService()

    def test_backup_and_restore_are_verified_and_preserve_the_previous_runtime(self):
        backup = self.service.create(self.runtime, self.root / "backup")
        with self.runtime.connect() as connection:
            connection.execute("INSERT INTO people(name) VALUES ('Later Person')")
        self.runtime.config_path.write_text(json.dumps({"changed": True}))

        with self.assertRaisesRegex(RuntimeError, "--replace"):
            self.service.restore(backup, self.runtime)
        safety_backup = self.service.restore(backup, self.runtime, replace=True)

        self.assertIsNotNone(safety_backup)
        self.assertTrue(safety_backup.is_dir())
        with self.runtime.connect() as connection:
            people = [row[0] for row in connection.execute("SELECT name FROM people")]
        self.assertEqual(people, ["Original Person"])
        self.assertEqual(
            json.loads(self.runtime.config_path.read_text()),
            {"RUNTIME_ENVIRONMENT": "synthetic"},
        )

    def test_restore_rejects_a_backup_whose_checksum_changed(self):
        backup = self.service.create(self.runtime, self.root / "backup")
        with (backup / "finance.sqlite3").open("ab") as stream:
            stream.write(b"tampered")

        with self.assertRaisesRegex(RuntimeError, "checksum failed"):
            self.service.restore(backup, RuntimeConfig(self.root / "restored"))

    def test_restore_allows_a_runtime_containing_only_configuration(self):
        backup = self.service.create(self.runtime, self.root / "backup")

        for replace in (False, True):
            with self.subTest(replace=replace):
                target = RuntimeConfig(self.root / f"config-only-{replace}")
                target.data_dir.mkdir()
                target.config_path.write_text(json.dumps({"placeholder": True}))

                safety_backup = self.service.restore(backup, target, replace=replace)

                self.assertIsNone(safety_backup)
                self.assertTrue(target.database_path.is_file())
                self.assertEqual(
                    json.loads(target.config_path.read_text()),
                    {"RUNTIME_ENVIRONMENT": "synthetic"},
                )
                with target.connect() as connection:
                    people = [row[0] for row in connection.execute("SELECT name FROM people")]
                self.assertEqual(people, ["Original Person"])


if __name__ == "__main__":
    unittest.main()
