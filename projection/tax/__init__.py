"""Tax calculation contracts and registered jurisdiction implementations."""

from .effective_marginal_rate import EffectiveMarginalRate
from .effective_marginal_rate_service import EffectiveMarginalRateService

__all__ = ["EffectiveMarginalRate", "EffectiveMarginalRateService"]
