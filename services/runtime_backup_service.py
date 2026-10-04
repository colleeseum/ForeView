# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from infrastructure.runtime_config import CONFIG_FILENAME, DATABASE_FILENAME, RuntimeConfig

MANIFEST_FILENAME = "manifest.json"


class RuntimeBackupService:
    """Create and restore verified, internally consistent runtime backups."""

    def create(self, runtime: RuntimeConfig, destination: Path) -> Path:
        destination = destination.expanduser().resolve()
        if destination.exists():
            raise RuntimeError(f"Backup destination already exists: {destination}")
        if not runtime.database_path.is_file():
            raise RuntimeError(f"Runtime database does not exist: {runtime.database_path}")
        destination.mkdir(parents=True)
        try:
            database_copy = destination / DATABASE_FILENAME
            with runtime.connect() as source, closing(sqlite3.connect(database_copy)) as target:
                with target:
                    source.backup(target)
            self._validate_database(database_copy)
            files = {DATABASE_FILENAME: self._sha256(database_copy)}
            if runtime.config_path.is_file():
                config_copy = destination / CONFIG_FILENAME
                shutil.copy2(runtime.config_path, config_copy)
                files[CONFIG_FILENAME] = self._sha256(config_copy)
            manifest = {
                "format_version": 1,
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "files": files,
            }
            (destination / MANIFEST_FILENAME).write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )
        except Exception:
            shutil.rmtree(destination)
            raise
        return destination

    def restore(
        self, backup: Path, runtime: RuntimeConfig, *, replace: bool = False
    ) -> Path | None:
        backup = backup.expanduser().resolve()
        files = self._verify(backup)
        existing_database = runtime.database_path.exists()
        if existing_database and not replace:
            raise RuntimeError("Runtime already contains data; pass --replace to restore over it")

        safety_backup = None
        if existing_database:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            safety_backup = runtime.data_dir.with_name(
                f"{runtime.data_dir.name}.pre-restore-{stamp}-{uuid.uuid4().hex[:8]}"
            )
            self.create(runtime, safety_backup)

        runtime.data_dir.mkdir(parents=True, exist_ok=True)
        temporary_database = runtime.data_dir / f".{DATABASE_FILENAME}.{uuid.uuid4().hex}.tmp"
        try:
            with (
                closing(sqlite3.connect(backup / DATABASE_FILENAME)) as source,
                closing(sqlite3.connect(temporary_database)) as target,
                target,
            ):
                source.backup(target)
            self._validate_database(temporary_database)
            os.replace(temporary_database, runtime.database_path)

            config_source = backup / CONFIG_FILENAME
            if CONFIG_FILENAME in files:
                temporary_config = runtime.data_dir / f".{CONFIG_FILENAME}.{uuid.uuid4().hex}.tmp"
                shutil.copy2(config_source, temporary_config)
                os.replace(temporary_config, runtime.config_path)
            elif runtime.config_path.exists():
                runtime.config_path.unlink()
        finally:
            temporary_database.unlink(missing_ok=True)
        return safety_backup

    def _verify(self, backup: Path) -> dict[str, str]:
        manifest_path = backup / MANIFEST_FILENAME
        try:
            manifest = json.loads(manifest_path.read_text())
            files = manifest["files"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise RuntimeError(f"Invalid backup manifest: {error}") from error
        if manifest.get("format_version") != 1 or not isinstance(files, dict):
            raise RuntimeError("Unsupported backup format")
        expected_files = {str(name): str(digest) for name, digest in files.items()}
        if DATABASE_FILENAME not in expected_files:
            raise RuntimeError("Backup manifest does not contain a database")
        for name, expected_hash in expected_files.items():
            if name not in {DATABASE_FILENAME, CONFIG_FILENAME}:
                raise RuntimeError(f"Unexpected file in backup manifest: {name}")
            path = backup / name
            if not path.is_file() or self._sha256(path) != expected_hash:
                raise RuntimeError(f"Backup checksum failed: {name}")
        self._validate_database(backup / DATABASE_FILENAME)
        return expected_files

    @staticmethod
    def _validate_database(path: Path) -> None:
        with closing(sqlite3.connect(path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise RuntimeError(f"SQLite integrity check failed for {path}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError(f"SQLite foreign-key check failed for {path}")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
