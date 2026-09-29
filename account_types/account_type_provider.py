from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountTypeProvider:
    """Classification and presentation contract for one account type."""

    key: str
    display_name: str
    tax_treatment: str
    liquidity_class: str
    supports_transactions: bool = True
    supports_holdings: bool = False
    supports_children: bool = True
    aliases: tuple[str, ...] = ()

    def names(self) -> tuple[str, ...]:
        return (self.key, self.display_name, *self.aliases)
