"""Explicit registry for public-rule source providers."""

from __future__ import annotations

from .public_rule_provider import PublicRuleProvider


class PublicRuleProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, PublicRuleProvider] = {}

    def register(self, provider: PublicRuleProvider) -> None:
        if provider.provider_id in self._providers:
            raise ValueError(f"Public-rule provider is already registered: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> PublicRuleProvider:
        try:
            return self._providers[provider_id]
        except KeyError as error:
            raise KeyError(f"Unknown public-rule provider: {provider_id}") from error

    def list_all(self) -> tuple[PublicRuleProvider, ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))
