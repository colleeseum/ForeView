from __future__ import annotations

import unittest
from decimal import Decimal

from domain.money import as_decimal, from_cents, optional_cents, to_cents


class MoneyTests(unittest.TestCase):
    def test_float_input_is_normalized_through_its_decimal_text(self):
        self.assertEqual(as_decimal(10.1), Decimal("10.10"))

    def test_cent_conversion_uses_financial_half_up_rounding(self):
        self.assertEqual(to_cents("12.345"), 1235)
        self.assertEqual(to_cents("-1.005"), -101)
        self.assertEqual(from_cents(1235), Decimal("12.35"))
        self.assertIsNone(optional_cents(None))

    def test_invalid_stored_cent_type_is_rejected(self):
        with self.assertRaises(TypeError):
            from_cents(12.5)


if __name__ == "__main__":
    unittest.main()
