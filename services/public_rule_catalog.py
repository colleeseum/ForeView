# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Load and verify version-controlled public-rule packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from domain.public_rule_package import PublicRulePackage
from projection.public_rules import PublicRuleSet


class PublicRuleCatalog:
    def __init__(self, root: Path) -> None:
        self._root = root

    def list_packages(self) -> tuple[PublicRulePackage, ...]:
        packages = []
        for manifest_path in sorted(self._root.glob("[0-9][0-9][0-9][0-9]/*/manifest.json")):
            packages.extend(self._load_manifest(manifest_path))
        return tuple(packages)

    def get(self, rule_set_id: str) -> PublicRulePackage | None:
        matches = [
            item for item in self.list_packages() if item.rule_set.rule_set_id == rule_set_id
        ]
        if len(matches) > 1:
            raise ValueError(f"Duplicate public rule-set id: {rule_set_id}")
        return matches[0] if matches else None

    def _load_manifest(self, manifest_path: Path) -> list[PublicRulePackage]:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tax_year = manifest.get("tax_year")
        jurisdiction = manifest.get("jurisdiction")
        if not isinstance(tax_year, int) or not isinstance(jurisdiction, str):
            raise ValueError(f"Invalid public-rule manifest identity: {manifest_path}")
        if manifest_path.parent.name != jurisdiction.lower() or manifest_path.parents[
            1
        ].name != str(tax_year):
            raise ValueError(
                f"Public-rule manifest path does not match its identity: {manifest_path}"
            )
        source_files = self._verify_sources(manifest_path.parent, manifest.get("sources"))
        records = manifest.get("rule_sets")
        if not isinstance(records, list) or not records:
            raise ValueError(f"Public-rule manifest has no rule sets: {manifest_path}")
        packages = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"Invalid rule-set record: {manifest_path}")
            rule_path = self._safe_file(manifest_path.parent, record.get("filename"))
            rule_set = PublicRuleSet.model_validate_json(rule_path.read_text(encoding="utf-8"))
            content_hash = rule_set.content_hash()
            if (
                rule_set.rule_set_id != record.get("rule_set_id")
                or rule_set.tax_year != tax_year
                or rule_set.jurisdiction != jurisdiction
                or content_hash != record.get("sha256")
            ):
                raise ValueError(f"Public rule set does not match its manifest: {rule_path}")
            packages.append(
                PublicRulePackage(
                    rule_set=rule_set,
                    content_hash=content_hash,
                    manifest_path=manifest_path,
                    source_files=source_files,
                )
            )
        return packages

    def _verify_sources(self, root: Path, records: object) -> tuple[Path, ...]:
        if not isinstance(records, list) or not records:
            raise ValueError(f"Public-rule manifest has no sources: {root}")
        paths = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"Invalid source record: {root}")
            path = self._safe_file(root, record.get("filename"))
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != record.get("sha256"):
                raise ValueError(f"Public-rule source hash mismatch: {path}")
            paths.append(path)
        return tuple(paths)

    @staticmethod
    def _safe_file(root: Path, filename: object) -> Path:
        if not isinstance(filename, str):
            raise ValueError(f"Invalid public-rule filename in {root}")
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe public-rule filename: {filename}")
        path = root / relative
        if not path.is_file():
            raise ValueError(f"Public-rule file is missing: {path}")
        return path
