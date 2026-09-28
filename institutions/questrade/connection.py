"""Runtime Questrade connection adapter."""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository

from .client import QuestradeClient
from .settings import QuestradeSettings


@dataclass(frozen=True)
class QuestradeConnectionProvider:
    """Expose Questrade configuration and synchronization through the connection contract."""

    settings: QuestradeSettings
    connect: Callable[[], sqlite3.Connection]
    client: QuestradeClient
    sync_connection: Callable[..., dict[str, object]]

    @property
    def institution_key(self) -> str:
        return "questrade"

    def configured_connections(self) -> tuple[str, ...]:
        return tuple(sorted(self.settings.profiles))

    def profile(self, connection_name: str) -> Mapping[str, str] | None:
        return self.settings.profiles.get(connection_name)

    def status(self) -> dict[str, object]:
        configured_connections = self.configured_connections()
        with self.connect() as connection:
            self.client.refresh_expiring_authorizations(connection)
            authorizations = QuestradeAuthorizationRepository(connection).list_all()
        return {
            "configured": bool(configured_connections),
            "configured_connections": configured_connections,
            "connected": bool(authorizations),
            "authorizations": [authorization.status() for authorization in authorizations],
        }

    def authorization_url(self, connection_name: str, state: str) -> str:
        profile = self.profile(connection_name)
        if not profile:
            raise RuntimeError(f"Questrade connection '{connection_name}' is not configured.")
        query = urllib.parse.urlencode(
            {
                "client_id": profile["consumer_key"],
                "response_type": "code",
                "redirect_uri": self.settings.required_redirect_uri(),
                "state": state,
            }
        )
        return f"{self.settings.authorize_url}?{query}"

    def complete_authorization(self, connection_name: str, code: str) -> None:
        profile = self.profile(connection_name)
        client_id = profile["consumer_key"] if profile else None
        if not code or not client_id:
            raise RuntimeError("Missing Questrade authorization code or client configuration.")
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": self.settings.required_redirect_uri(),
        }
        if profile and profile.get("client_secret"):
            form["client_secret"] = profile["client_secret"]
        self.client.validate_url(self.settings.token_url)
        try:
            # The URL is restricted to Questrade HTTPS hosts above.
            with urllib.request.urlopen(  # nosec B310
                urllib.request.Request(
                    self.settings.token_url,
                    data=urllib.parse.urlencode(form).encode(),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                        "User-Agent": "RetirementModel/1.0",
                    },
                ),
                timeout=20,
            ) as response:
                token_data = json.loads(response.read().decode())
            encrypted = self.settings.cipher()
            access_expires = (
                datetime.now(UTC) + timedelta(seconds=int(token_data.get("expires_in", 1800)))
            ).isoformat(timespec="seconds")
            with self.connect() as connection:
                QuestradeAuthorizationRepository(connection).save_tokens(
                    connection_name,
                    access_token=encrypted.encrypt(token_data["access_token"].encode()).decode(),
                    refresh_token=encrypted.encrypt(token_data["refresh_token"].encode()).decode(),
                    api_server=token_data.get("api_server", ""),
                    access_expires_at=access_expires,
                    refresh_expires_at=token_data.get("refresh_token_expires_at"),
                )
        except urllib.error.HTTPError as error:
            try:
                detail = error.read().decode(errors="replace").strip()
            finally:
                error.close()
            message = f"Questrade token exchange failed ({error.code})"
            if detail:
                message = f"{message}: {detail[:300]}"
            raise RuntimeError(message) from error
        except (urllib.error.URLError, KeyError, ValueError) as error:
            raise RuntimeError(str(error)) from error

    def refresh(self, connection_name: str) -> None:
        with self.connect() as connection:
            authorization = QuestradeAuthorizationRepository(connection).get_by_name(
                connection_name
            )
            if authorization is None:
                raise RuntimeError("No saved Questrade authorization")
            self.client.refresh_authorization(connection, authorization)

    def synchronize(
        self, connection_name: str, *, fetch_from: str | None = None
    ) -> dict[str, object]:
        if fetch_from is None:
            return self.sync_connection(connection_name)
        return self.sync_connection(connection_name, fetch_from)
