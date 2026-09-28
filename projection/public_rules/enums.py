"""Enumerations used by the public-rule schema."""

from __future__ import annotations

from enum import StrEnum


class RuleStatus(StrEnum):
    OFFICIAL = "OFFICIAL"
    PROJECTED = "PROJECTED"


class RuleUnit(StrEnum):
    CAD = "CAD"
    RATE = "RATE"
    COUNT = "COUNT"
    YEARS = "YEARS"


class IndexingMechanism(StrEnum):
    NONE = "NONE"
    CPI = "CPI"
    QUEBEC_INDEXATION = "QUEBEC_INDEXATION"
    WAGE_GROWTH = "WAGE_GROWTH"
    FIXED_RATE = "FIXED_RATE"
    STATUTORY_SCHEDULE = "STATUTORY_SCHEDULE"


class RoundingMode(StrEnum):
    NEAREST = "NEAREST"
    UP = "UP"
    DOWN = "DOWN"
