"""Registry-backed access to jurisdiction effective marginal-rate calculators."""

from __future__ import annotations

from typing import Protocol

from projection.public_rules import PublicRuleSet

from .effective_marginal_rate import EffectiveMarginalRate
from .manitoba_effective_marginal_rate_calculator import ManitobaEffectiveMarginalRateCalculator
from .ontario_effective_marginal_rate_calculator import OntarioEffectiveMarginalRateCalculator
from .quebec_effective_marginal_rate_calculator import QuebecEffectiveMarginalRateCalculator
from .standard_effective_marginal_rate_calculator import StandardEffectiveMarginalRateCalculator

_STANDARD_JURISDICTIONS = (
    "CA-AB",
    "CA-BC",
    "CA-NB",
    "CA-NL",
    "CA-NS",
    "CA-NT",
    "CA-NU",
    "CA-PE",
    "CA-SK",
    "CA-YT",
)


class _Calculator(Protocol):
    jurisdiction: str

    def calculate(
        self, federal: PublicRuleSet, provincial: PublicRuleSet
    ) -> tuple[EffectiveMarginalRate, ...]: ...


class EffectiveMarginalRateService:
    def __init__(self) -> None:
        calculators: tuple[_Calculator, ...] = (
            *(StandardEffectiveMarginalRateCalculator(code) for code in _STANDARD_JURISDICTIONS),
            ManitobaEffectiveMarginalRateCalculator(),
            OntarioEffectiveMarginalRateCalculator(),
            QuebecEffectiveMarginalRateCalculator(),
        )
        self._calculators = {item.jurisdiction: item for item in calculators}

    def calculate(
        self, federal: PublicRuleSet, provincial: PublicRuleSet
    ) -> tuple[EffectiveMarginalRate, ...] | None:
        if federal.tax_year != provincial.tax_year:
            raise ValueError("Federal and provincial rule sets must use the same tax year")
        calculator = self._calculators.get(provincial.jurisdiction)
        return calculator.calculate(federal, provincial) if calculator else None
