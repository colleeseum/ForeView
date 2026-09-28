from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountOwnership:
    """One person's ownership share in an account."""

    account_id: int
    person_id: int
    share: float
