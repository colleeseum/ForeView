# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import dataclasses
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock

from institution_support.connection_capability import ConnectionOperation
from institution_support.document_importer import DocumentImporter
from institution_support.institution_provider import InstitutionProvider
from institution_support.registry import InstitutionRegistry, institution_registry
from institutions.questrade import QuestradeConnectionProvider
from institutions.questrade.settings import QuestradeSettings


class InstitutionRegistryTests(unittest.TestCase):
    def test_default_registry_groups_multiple_formats_under_the_institution(self):
        registry = institution_registry()

        rbc = registry.find("Royal Bank of Canada")
        self.assertIsNotNone(rbc)
        self.assertEqual(rbc.key, "rbc")
        self.assertEqual(len(rbc.importers), 4)
        self.assertEqual(
            {importer.document_type for importer in rbc.importers},
            {"account", "gic", "tfsa"},
        )
        self.assertIsNotNone(rbc.csv_parser)
        self.assertEqual(rbc.balance_excluded_sources, ("rbc_tfsa_pdf",))
        self.assertEqual(rbc.balance_including_snapshot_sources, ("RBC TFSA PDF",))
        self.assertIn("rbc_tfsa_pdf", registry.balance_excluded_sources())
        self.assertIs(registry.csv_parsers("RBC")[0], rbc.csv_parser)
        self.assertIn(rbc.csv_parser, registry.csv_parsers())

        questrade = registry.find("Questrade")
        self.assertEqual(questrade.importers, ())
        self.assertEqual(
            questrade.connection.operations,
            {
                ConnectionOperation.AUTHORIZE,
                ConnectionOperation.REFRESH,
                ConnectionOperation.SYNC,
            },
        )

    def test_registry_limits_importers_to_known_institution_aliases(self):
        registry = institution_registry()

        self.assertEqual(len(registry.importers("RBC")), 4)
        self.assertEqual(len(registry.importers("Royal Bank")), 4)
        self.assertEqual(registry.importers("Unknown Bank"), ())
        self.assertGreater(len(registry.importers()), 3)

    def test_provider_contract_is_immutable_and_rejects_ambiguous_names(self):
        first = InstitutionProvider("first", "First Bank", aliases=("Shared",))
        second = InstitutionProvider("second", "Second Bank", aliases=("Shared",))

        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.display_name = "Changed"
        with self.assertRaisesRegex(ValueError, "already registered"):
            InstitutionRegistry((first, second))

    def test_registry_rejects_non_calver_module_versions(self):
        provider = InstitutionProvider("old", "Old Bank", version="0.1.0")

        with self.assertRaisesRegex(ValueError, "must use CalVer"):
            InstitutionRegistry((provider,))

    def test_registry_rejects_duplicate_importer_names(self):
        importer = DocumentImporter("Statement", "account", lambda _: True, Mock(), "load", "")
        first = InstitutionProvider("first", "First", importers=(importer,))
        second = InstitutionProvider("second", "Second", importers=(importer,))

        with self.assertRaisesRegex(ValueError, "Importer 'Statement'"):
            InstitutionRegistry((first, second))

    def test_import_help_is_assembled_from_provider_metadata(self):
        help_text = institution_registry().import_help()

        self.assertIn("RBC deposit statements", help_text)
        self.assertIn("Sun Life Group Choices", help_text)
        self.assertIn("Standard Date/Amount CSV", help_text)


class QuestradeConnectionProviderTests(unittest.TestCase):
    def test_adapter_exposes_sorted_profiles_and_delegates_sync(self):
        synchronize = Mock(return_value={"connection": "primary"})
        adapter = QuestradeConnectionProvider(
            QuestradeSettings(
                profiles={
                    "primary": {"consumer_key": "one"},
                    "alex": {"consumer_key": "two"},
                },
                redirect_uri="https://finance.example/callback",
                token_key=None,
            ),
            Mock(),
            Mock(),
            synchronize,
        )

        self.assertEqual(adapter.institution_key, "questrade")
        self.assertEqual(adapter.configured_connections(), ("alex", "primary"))
        self.assertEqual(adapter.profile("primary"), {"consumer_key": "one"})
        self.assertIsNone(adapter.profile("missing"))
        self.assertEqual(adapter.synchronize("primary"), {"connection": "primary"})
        synchronize.assert_called_once_with("primary")

    def test_security_holding_institutions_are_declared_by_providers(self):
        registry = institution_registry()

        for name in ("Questrade", "Sun Life", "Sunlife", "manulife"):
            with self.subTest(name=name):
                self.assertTrue(registry.holds_securities(name))
        for name in ("RBC", "EQ Bank", "Unknown bank", None):
            with self.subTest(name=name):
                self.assertFalse(registry.holds_securities(name))


class InstitutionDiscoveryTests(unittest.TestCase):
    PROVIDER = (
        "from institution_support.institution_provider import InstitutionProvider\n\n"
        "def provider():\n"
        "    return InstitutionProvider(key={key!r}, display_name={name!r})\n"
    )

    def _package(self, files: dict[str, str]) -> str:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        name = f"dropin_{uuid.uuid4().hex}"
        for relative, content in {"__init__.py": "", **files}.items():
            path = root / name / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        sys.path.insert(0, str(root))
        self.addCleanup(sys.path.remove, str(root))
        return name

    def test_file_and_directory_modules_are_discovered_in_name_order(self):
        package = self._package(
            {
                "zeta_bank.py": self.PROVIDER.format(key="zeta", name="Zeta Bank"),
                "alpha_bank/__init__.py": self.PROVIDER.format(key="alpha", name="Alpha Bank"),
                "_helpers.py": "VALUE = 1\n",
            }
        )

        registry = institution_registry(package)

        self.assertEqual([provider.key for provider in registry.providers], ["alpha", "zeta"])
        self.assertEqual(registry.find("Zeta Bank").key, "zeta")  # type: ignore[union-attr]

    def test_module_without_provider_is_rejected(self):
        package = self._package({"broken_bank.py": "VALUE = 1\n"})

        with self.assertRaisesRegex(TypeError, "broken_bank.*must define provider"):
            institution_registry(package)
