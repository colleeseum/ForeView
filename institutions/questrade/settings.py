"""Questrade configuration read from the runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.fernet import Fernet

from institution_support.runtime_context import RuntimeContext

AUTHORIZE_URL = "https://login.questrade.com/oauth2/authorize"
# This is a public OAuth endpoint, not a credential.
TOKEN_URL = "https://login.questrade.com/oauth2/token"  # nosec B105


@dataclass(frozen=True)
class QuestradeSettings:
    """Configured Questrade logins, OAuth endpoints, and the token encryption key."""

    profiles: Mapping[str, Mapping[str, str]]
    redirect_uri: str
    token_key: str | None
    authorize_url: str = AUTHORIZE_URL
    token_url: str = TOKEN_URL

    @classmethod
    def from_runtime(cls, runtime: RuntimeContext) -> QuestradeSettings:
        profiles: dict[str, dict[str, str]] = {}
        configured = runtime.config.get("QUESTRADE_CONNECTIONS", [])
        if isinstance(configured, list):
            for item in configured:
                if isinstance(item, dict) and item.get("name") and item.get("consumer_key"):
                    profile = {
                        "consumer_key": str(item["consumer_key"]),
                        "client_secret": str(item.get("client_secret", "")),
                    }
                    if item.get("history_start"):
                        # First sync of each account fetches activity from this date.
                        profile["history_start"] = str(item["history_start"])
                    profiles[str(item["name"])] = profile
        legacy_key = runtime.setting("QUESTRADE_CONSUMER_KEY") or runtime.setting(
            "QUESTRADE_CLIENT_ID"
        )
        if legacy_key and "default" not in profiles:
            profiles["default"] = {
                "consumer_key": legacy_key,
                "client_secret": runtime.setting("QUESTRADE_CLIENT_SECRET") or "",
            }
        return cls(
            profiles=profiles,
            redirect_uri=runtime.setting("QUESTRADE_REDIRECT_URI") or "",
            token_key=runtime.setting("RETIREMENT_TOKEN_KEY"),
        )

    def required_redirect_uri(self) -> str:
        if not self.redirect_uri:
            raise RuntimeError("QUESTRADE_REDIRECT_URI is not configured.")
        return self.redirect_uri

    def cipher(self) -> Fernet:
        if not self.token_key:
            raise RuntimeError("RETIREMENT_TOKEN_KEY is not configured")
        return Fernet(self.token_key.encode())
