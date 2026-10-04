# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Strict accessors for calculation inputs in public-rule sets."""

from __future__ import annotations

from decimal import Decimal

from projection.public_rules import PublicRuleSet, TaxBracketSchedule


def schedule(rule_set: PublicRuleSet, code: str) -> TaxBracketSchedule:
    matches = [item for item in rule_set.tax_brackets if item.code == code]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {code} schedule in {rule_set.rule_set_id}")
    return matches[0]


def parameter(rule_set: PublicRuleSet, code: str) -> Decimal:
    parameters = (
        *rule_set.credits,
        *rule_set.payroll_parameters,
        *rule_set.contribution_limits,
        *rule_set.other_parameters,
    )
    matches = [item.value for item in parameters if item.code == code]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {code} parameter in {rule_set.rule_set_id}")
    return matches[0]
