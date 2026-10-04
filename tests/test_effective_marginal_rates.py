# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import unittest
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from projection.tax import EffectiveMarginalRateService
from services.public_rule_catalog import PublicRuleCatalog


class EffectiveMarginalRateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = PublicRuleCatalog(Path(__file__).parents[1] / "public_rules")
        cls.service = EffectiveMarginalRateService()

    def test_quebec_schedules_match_independent_taxtips_reference(self):
        # https://www.taxtips.ca/taxrates/qc.htm, ordinary other income column.
        expected = {
            2025: (
                ("53255", "26.11"),
                ("57375", "31.11"),
                ("106495", "36.12"),
                ("114750", "41.12"),
                ("129590", "45.71"),
                ("177882", "47.46"),
                ("253414", "50.22"),
                (None, "53.31"),
            ),
            2026: (
                ("54345", "25.69"),
                ("58523", "30.69"),
                ("108680", "36.12"),
                ("117045", "41.12"),
                ("132245", "45.71"),
                ("181440", "47.46"),
                ("258482", "50.21"),
                (None, "53.31"),
            ),
        }
        for year, reference in expected.items():
            with self.subTest(year=year):
                self.assertEqual(self._display_schedule("ca-qc", year), reference)

    def test_ontario_schedules_match_independent_taxtips_reference(self):
        # https://www.taxtips.ca/taxrates/on.htm, ordinary other income column.
        expected = {
            2025: (
                ("52886", "19.55"),
                ("57375", "23.65"),
                ("93132", "29.65"),
                ("105775", "31.48"),
                ("109727", "33.89"),
                ("114750", "37.91"),
                ("150000", "43.41"),
                ("177882", "44.97"),
                ("220000", "48.28"),
                ("253414", "49.84"),
                (None, "53.53"),
            ),
            2026: (
                ("53891", "19.05"),
                ("58523", "23.15"),
                ("94907", "29.65"),
                ("107785", "31.48"),
                ("111814", "33.89"),
                ("117045", "37.91"),
                ("150000", "43.41"),
                ("181440", "44.97"),
                ("220000", "48.26"),
                ("258482", "49.82"),
                (None, "53.53"),
            ),
        }
        for year, reference in expected.items():
            with self.subTest(year=year):
                actual = self._display_schedule("ca-on", year)
                self.assertEqual(len(actual), len(reference))
                for actual_row, reference_row in zip(actual, reference, strict=True):
                    self.assertEqual(actual_row[1], reference_row[1])
                    if reference_row[0] is None:
                        self.assertIsNone(actual_row[0])
                    else:
                        self.assertLessEqual(
                            abs(Decimal(actual_row[0]) - Decimal(reference_row[0])),
                            Decimal("6"),
                            "Official-rule Ontario transition differs materially from TaxTips",
                        )

    def test_every_province_and_territory_has_a_registered_calculator(self):
        for jurisdiction_slug in (
            "ca-ab",
            "ca-bc",
            "ca-mb",
            "ca-nb",
            "ca-nl",
            "ca-ns",
            "ca-nt",
            "ca-nu",
            "ca-on",
            "ca-pe",
            "ca-qc",
            "ca-sk",
            "ca-yt",
        ):
            for year in (2025, 2026):
                with self.subTest(jurisdiction=jurisdiction_slug, year=year):
                    self.assertTrue(self._display_schedule(jurisdiction_slug, year))

    def test_standard_calculator_matches_alberta_reference_table(self):
        # https://www.taxtips.ca/taxrates/ab.htm, ordinary other income column.
        expected = {
            2025: (
                ("57375", "22.50"),
                ("60000", "28.50"),
                ("114750", "30.50"),
                ("151234", "36.00"),
                ("177882", "38.00"),
                ("181481", "41.31"),
                ("241974", "42.31"),
                ("253414", "43.31"),
                ("362961", "47.00"),
                (None, "48.00"),
            ),
            2026: (
                ("58523", "22.00"),
                ("61200", "28.50"),
                ("117045", "30.50"),
                ("154259", "36.00"),
                ("181440", "38.00"),
                ("185111", "41.29"),
                ("246813", "42.29"),
                ("258482", "43.29"),
                ("370220", "47.00"),
                (None, "48.00"),
            ),
        }
        for year, reference in expected.items():
            with self.subTest(year=year):
                self.assertEqual(self._display_schedule("ca-ab", year), reference)

    def test_all_jurisdiction_endpoint_rates_match_independent_reference(self):
        # TaxTips provincial tables, ordinary other income columns for 2025 and 2026.
        expected = {
            "ca-ab": {2025: ("22.50", "48.00"), 2026: ("22.00", "48.00")},
            "ca-bc": {2025: ("19.56", "53.50"), 2026: ("19.60", "53.50")},
            "ca-mb": {2025: ("25.30", "50.40"), 2026: ("24.80", "50.40")},
            "ca-nb": {2025: ("23.90", "52.50"), 2026: ("23.40", "52.50")},
            "ca-nl": {2025: ("23.20", "54.80"), 2026: ("22.70", "54.80")},
            "ca-ns": {2025: ("23.29", "54.00"), 2026: ("22.79", "54.00")},
            "ca-nt": {2025: ("20.40", "47.05"), 2026: ("19.90", "47.05")},
            "ca-nu": {2025: ("18.50", "44.50"), 2026: ("18.00", "44.50")},
            "ca-on": {2025: ("19.55", "53.53"), 2026: ("19.05", "53.53")},
            "ca-pe": {2025: ("24.00", "52.00"), 2026: ("23.50", "53.00")},
            "ca-qc": {2025: ("26.11", "53.31"), 2026: ("25.69", "53.31")},
            "ca-sk": {2025: ("25.00", "47.50"), 2026: ("24.50", "47.50")},
            "ca-yt": {2025: ("20.90", "48.00"), 2026: ("20.40", "48.00")},
        }
        for jurisdiction, annual in expected.items():
            for year, rates in annual.items():
                with self.subTest(jurisdiction=jurisdiction, year=year):
                    schedule = self._display_schedule(jurisdiction, year)
                    self.assertEqual((schedule[0][1], schedule[-1][1]), rates)

    def test_manitoba_bpa_phaseout_matches_independent_reference(self):
        # https://www.taxtips.ca/taxrates/mb.htm, ordinary other income column.
        expected_rates = {
            2025: {
                "200000": "46.71",
                "253414": "47.56",
                "400000": "51.25",
                None: "50.40",
            },
            2026: {
                "200000": "46.69",
                # Exact CRA BPA formula rounds to 47.55%; TaxTips displays 47.54%.
                "258482": "47.55",
                "400000": "51.25",
                None: "50.40",
            },
        }
        for year, reference in expected_rates.items():
            with self.subTest(year=year):
                actual = dict(self._display_schedule("ca-mb", year))
                self.assertEqual({bound: actual[bound] for bound in reference}, reference)

    def _display_schedule(
        self, jurisdiction_slug: str, year: int
    ) -> tuple[tuple[str | None, str], ...]:
        federal = self.catalog.get(f"ca-{year}-official")
        provincial = self.catalog.get(f"{jurisdiction_slug}-{year}-official")
        self.assertIsNotNone(federal)
        self.assertIsNotNone(provincial)
        result = self.service.calculate(federal.rule_set, provincial.rule_set)
        self.assertIsNotNone(result)
        return tuple(
            (
                str(item.upper_bound) if item.upper_bound is not None else None,
                str((item.rate * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            )
            for item in result
        )
