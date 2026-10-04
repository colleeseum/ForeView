from __future__ import annotations

import unittest

from account_types import account_type_registry


class AccountTypeRegistryTests(unittest.TestCase):
    def test_discovers_resp_alongside_existing_account_types(self) -> None:
        registry = account_type_registry()

        self.assertEqual(
            [item.key for item in registry.providers], ["non_registered", "resp", "rrsp", "tfsa"]
        )
        self.assertEqual(registry.get("resp").tax_treatment, "education_assistance_withdrawal")
        self.assertEqual(registry.get("resp").liquidity_class, "restricted")

    def test_unknown_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown account type"):
            account_type_registry().get("made_up")
