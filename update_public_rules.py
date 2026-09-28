"""Retrieve official public financial rules into version-controlled packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from projection.public_rules import PublicRuleSet
from projection.rule_update import (
    FederalRuleProvider,
    HttpSourceRetriever,
    PublicRuleProviderRegistry,
    PublicRuleUpdateService,
    QuebecRuleProvider,
    cra_jurisdiction_providers,
)


def build_registry() -> PublicRuleProviderRegistry:
    registry = PublicRuleProviderRegistry()
    registry.register(FederalRuleProvider())
    registry.register(QuebecRuleProvider())
    for provider in cra_jurisdiction_providers():
        registry.register(provider)
    return registry


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve official public rules into version-controlled annual packages."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=date.today().year,
        help="Tax year to retrieve; defaults to the current year",
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=tuple(provider.provider_id for provider in build_registry().list_all()),
        dest="providers",
        help="Provider to update; repeat to select multiple providers",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("public_rules"),
        help="Version-controlled public-rule root directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace packages that are already present for the selected year",
    )
    return parser.parse_args(arguments)


def package_is_downloaded(
    output_directory: Path, tax_year: int, provider_id: str, jurisdiction: str
) -> bool:
    manifest_path = output_directory / str(tax_year) / jurisdiction.lower() / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    identity_matches = (
        manifest.get("provider_id") == provider_id
        and manifest.get("jurisdiction") == jurisdiction
        and manifest.get("tax_year") == tax_year
    )
    if not identity_matches:
        return False
    package_directory = manifest_path.parent
    return _records_match(
        package_directory, manifest.get("rule_sets"), canonical_rules=True
    ) and _records_match(package_directory, manifest.get("sources"), canonical_rules=False)


def _records_match(package_directory: Path, records: object, *, canonical_rules: bool) -> bool:
    if not isinstance(records, list) or not records:
        return False
    for record in records:
        if not isinstance(record, dict):
            return False
        filename = record.get("filename")
        expected_hash = record.get("sha256")
        if not isinstance(filename, str) or not isinstance(expected_hash, str):
            return False
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            return False
        try:
            content = (package_directory / relative).read_bytes()
            actual_hash = (
                PublicRuleSet.model_validate_json(content).content_hash()
                if canonical_rules
                else hashlib.sha256(content).hexdigest()
            )
        except (OSError, ValueError):
            return False
        if actual_hash != expected_hash:
            return False
    return True


def providers_to_update(
    registry: PublicRuleProviderRegistry,
    output_directory: Path,
    tax_year: int,
    provider_ids: list[str],
    *,
    force: bool,
) -> tuple[list[str], list[str]]:
    if force:
        return provider_ids, []
    pending = []
    skipped = []
    for provider_id in provider_ids:
        provider = registry.get(provider_id)
        if package_is_downloaded(
            output_directory,
            tax_year,
            provider.provider_id,
            provider.jurisdiction,
        ):
            skipped.append(provider_id)
        else:
            pending.append(provider_id)
    return pending, skipped


def main() -> None:
    arguments = parse_arguments()
    registry = build_registry()
    providers = arguments.providers or [provider.provider_id for provider in registry.list_all()]
    providers, skipped = providers_to_update(
        registry,
        arguments.output,
        arguments.year,
        providers,
        force=arguments.force,
    )
    for provider_id in skipped:
        print(f"{provider_id}: already downloaded for {arguments.year}; skipped")
    if not providers:
        print(f"{arguments.year}: all selected public-rule packages are already downloaded.")
        return
    results = PublicRuleUpdateService(
        registry,
        HttpSourceRetriever(),
    ).update(arguments.year, providers, arguments.output)
    for result in results:
        print(
            f"{result.provider_id}: {result.package_directory} "
            f"({len(result.rule_set_hashes)} rule set, {len(result.source_hashes)} sources)"
        )
    print("Rule packages require hash approval in each runtime database before use.")


if __name__ == "__main__":
    main()
