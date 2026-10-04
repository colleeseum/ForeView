# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
import unittest
from datetime import date

from pydantic import ValidationError

from projection.public_rules import (
    IndexingMechanism,
    IndexingMetadata,
    ProjectionAssumption,
    PublicRuleSet,
    RoundingMetadata,
    RoundingMode,
    RuleParameter,
    RuleSource,
    RuleStatus,
    RuleUnit,
    TaxBracket,
    TaxBracketSchedule,
)


def source() -> RuleSource:
    return RuleSource(
        source_id="official-example",
        title="Synthetic official publication",
        publisher="Example public authority",
        url="https://example.invalid/public-rules",
        published_on=date(2026, 1, 1),
        accessed_on=date(2026, 1, 2),
    )


def no_indexing() -> IndexingMetadata:
    return IndexingMetadata(mechanism=IndexingMechanism.NONE)


def official_rule_set(**changes) -> PublicRuleSet:
    values = {
        "rule_set_id": "ca-qc-2026-test",
        "jurisdiction": "CA-QC",
        "tax_year": 2026,
        "status": RuleStatus.OFFICIAL,
        "published_on": date(2026, 1, 1),
        "effective_from": date(2026, 1, 1),
        "effective_to": date(2026, 12, 31),
        "sources": (source(),),
        "tax_brackets": (
            TaxBracketSchedule(
                code="income_tax",
                brackets=(
                    TaxBracket(upper_bound="50000.00", rate="0.15"),
                    TaxBracket(upper_bound=None, rate="0.20"),
                ),
                source_ids=("official-example",),
                threshold_indexing=IndexingMetadata(
                    mechanism=IndexingMechanism.CPI,
                    reference_series="synthetic-cpi",
                    lag_years=1,
                    rounding=RoundingMetadata(increment="1", mode=RoundingMode.NEAREST),
                ),
                rate_indexing=no_indexing(),
            ),
        ),
        "credits": (
            RuleParameter(
                code="basic_personal_amount",
                value="15000.00",
                unit=RuleUnit.CAD,
                source_ids=("official-example",),
                indexing=no_indexing(),
            ),
        ),
        "payroll_parameters": (
            RuleParameter(
                code="payroll_rate",
                value="0.01",
                unit=RuleUnit.RATE,
                source_ids=("official-example",),
                indexing=IndexingMetadata(
                    mechanism=IndexingMechanism.WAGE_GROWTH,
                    reference_series="synthetic-wages",
                ),
            ),
        ),
        "contribution_limits": (
            RuleParameter(
                code="registered_limit",
                value="30000",
                unit=RuleUnit.CAD,
                source_ids=("official-example",),
                indexing=IndexingMetadata(mechanism=IndexingMechanism.STATUTORY_SCHEDULE),
            ),
        ),
    }
    values.update(changes)
    return PublicRuleSet(**values)


class PublicRuleContractTests(unittest.TestCase):
    def test_official_rule_set_serializes_and_hashes_deterministically(self):
        first = official_rule_set()
        second = official_rule_set(
            credits=(
                RuleParameter(
                    code="basic_personal_amount",
                    value="15000.0000",
                    unit="CAD",
                    source_ids=("official-example",),
                    indexing={"mechanism": "NONE"},
                ),
            ),
        )
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first.content_hash(), second.content_hash())
        data = json.loads(first.canonical_json())
        self.assertEqual(data["credits"][0]["value"], "15000")
        self.assertEqual(data["tax_brackets"][0]["brackets"][0]["rate"], "0.15")
        restored = PublicRuleSet.model_validate_json(first.canonical_json())
        self.assertEqual(restored.content_hash(), first.content_hash())

    def test_decimal_fields_reject_binary_floats(self):
        with self.assertRaises(ValidationError):
            RuleParameter(
                code="bad_rate",
                value=0.15,
                unit="RATE",
                source_ids=("official-example",),
                indexing={"mechanism": "NONE"},
            )

    def test_brackets_require_increasing_bounds_and_open_final_bracket(self):
        with self.assertRaises(ValidationError):
            TaxBracketSchedule(
                code="bad_brackets",
                brackets=(
                    {"upper_bound": "50000", "rate": "0.1"},
                    {"upper_bound": "40000", "rate": "0.2"},
                ),
                source_ids=("official-example",),
                threshold_indexing={"mechanism": "NONE"},
                rate_indexing={"mechanism": "NONE"},
            )
        with self.assertRaises(ValidationError):
            TaxBracketSchedule(
                code="closed_schedule",
                brackets=({"upper_bound": "50000", "rate": "0.1"},),
                source_ids=("official-example",),
                threshold_indexing={"mechanism": "NONE"},
                rate_indexing={"mechanism": "NONE"},
            )

    def test_rule_set_rejects_missing_provenance(self):
        bad_credit = RuleParameter(
            code="unknown_source",
            value="1",
            unit="CAD",
            source_ids=("missing",),
            indexing={"mechanism": "NONE"},
        )
        with self.assertRaises(ValidationError):
            official_rule_set(credits=(bad_credit,))

    def test_projected_rules_require_ancestry_and_assumptions(self):
        with self.assertRaises(ValidationError):
            official_rule_set(status="PROJECTED")
        projected = official_rule_set(
            rule_set_id="ca-qc-2027-projected",
            tax_year=2027,
            status="PROJECTED",
            published_on=None,
            effective_from=date(2027, 1, 1),
            effective_to=date(2027, 12, 31),
            based_on_rule_set_id="ca-qc-2026-test",
            projection_assumptions=(ProjectionAssumption(code="cpi", value="0.02", unit="RATE"),),
        )
        self.assertEqual(projected.status, RuleStatus.PROJECTED)
        with self.assertRaises(ValidationError):
            official_rule_set(
                status="PROJECTED",
                based_on_rule_set_id="ca-qc-2026-test",
                projection_assumptions=({"code": "cpi", "value": "0.02", "unit": "RATE"},),
            )

    def test_indexing_supports_distinct_mechanisms_and_rounding(self):
        mechanisms = {
            IndexingMechanism.NONE,
            IndexingMechanism.CPI,
            IndexingMechanism.QUEBEC_INDEXATION,
            IndexingMechanism.WAGE_GROWTH,
            IndexingMechanism.FIXED_RATE,
            IndexingMechanism.STATUTORY_SCHEDULE,
        }
        built = {
            IndexingMetadata(
                mechanism=mechanism,
                fixed_rate="0.02" if mechanism == IndexingMechanism.FIXED_RATE else None,
            ).mechanism
            for mechanism in mechanisms
        }
        self.assertEqual(built, mechanisms)
        with self.assertRaises(ValidationError):
            IndexingMetadata(mechanism="FIXED_RATE")
        with self.assertRaises(ValidationError):
            IndexingMetadata(mechanism="NONE", reference_series="cpi")

    def test_effective_dates_must_match_tax_year(self):
        with self.assertRaises(ValidationError):
            official_rule_set(effective_to=date(2027, 1, 1))

    def test_malformed_json_and_impossible_source_dates_are_rejected(self):
        with self.assertRaises(ValidationError):
            PublicRuleSet.model_validate_json('{"rule_set_id":')
        with self.assertRaises(ValidationError):
            RuleSource(
                source_id="bad-date",
                title="Synthetic",
                publisher="Authority",
                url="https://example.invalid/rules",
                published_on=date(2026, 2, 1),
                accessed_on=date(2026, 1, 1),
            )

    def test_json_schema_exports_without_runtime_dependencies(self):
        schema = PublicRuleSet.model_json_schema()
        self.assertEqual(schema["title"], "PublicRuleSet")
        self.assertIn("tax_brackets", schema["properties"])
        self.assertIn("projection_assumptions", schema["properties"])


if __name__ == "__main__":
    unittest.main()
