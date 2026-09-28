"""Build a compact schedule from exact calculation breakpoints."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from decimal import Decimal

from .effective_marginal_rate import EffectiveMarginalRate


def build_schedule(
    breakpoints: Iterable[Decimal], rate_at: Callable[[Decimal], Decimal]
) -> tuple[EffectiveMarginalRate, ...]:
    ordered = sorted(set(breakpoints))
    result: list[EffectiveMarginalRate] = []
    lower = Decimal("0")
    for upper in (*ordered, None):
        sample = lower + Decimal("0.01")
        rate = rate_at(sample)
        if result and result[-1].rate == rate:
            result[-1] = EffectiveMarginalRate(upper_bound=upper, rate=rate)
        else:
            result.append(EffectiveMarginalRate(upper_bound=upper, rate=rate))
        if upper is not None:
            lower = upper
    return tuple(result)
