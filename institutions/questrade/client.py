from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet

from domain.questrade_authorization import QuestradeAuthorization
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository

from .settings import QuestradeSettings
from .unauthorized import QuestradeUnauthorized


class QuestradeClient:
    """Questrade OAuth token and authenticated API client."""

    def __init__(self, settings: QuestradeSettings) -> None:
        self._settings = settings

    @staticmethod
    def validate_url(url: str) -> str:
        """Allow Questrade HTTPS endpoints and reject local or unexpected URL schemes."""
        parsed = urllib.parse.urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        allowed_host = hostname == "login.questrade.com" or hostname.endswith(".iq.questrade.com")
        if parsed.scheme != "https" or not allowed_host:
            raise RuntimeError("Questrade returned an invalid service URL")
        return url

    def cipher(self) -> Fernet:
        return self._settings.cipher()

    def refresh_authorization(
        self, connection: sqlite3.Connection, authorization: QuestradeAuthorization
    ) -> None:
        """Refresh and persist one Questrade authorization token."""
        cipher = self.cipher()
        refresh_token = cipher.decrypt(authorization.refresh_token.encode()).decode()
        form = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        self.validate_url(self._settings.token_url)
        try:
            # The URL is restricted to Questrade HTTPS hosts above.
            with urllib.request.urlopen(  # nosec B310
                urllib.request.Request(
                    self._settings.token_url,
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
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode(errors="replace").strip()
            finally:
                exc.close()
            message = f"Questrade token refresh failed ({exc.code})"
            if detail:
                message = f"{message}: {detail[:300]}"
            raise RuntimeError(message) from exc
        except (urllib.error.URLError, ValueError) as exc:
            raise RuntimeError(f"Questrade token refresh failed: {exc}") from exc

        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError("Questrade token refresh returned no access token")
        access_expires = (
            datetime.now(UTC) + timedelta(seconds=int(token_data.get("expires_in", 1800)))
        ).isoformat(timespec="seconds")
        new_refresh_token = token_data.get("refresh_token", refresh_token)
        QuestradeAuthorizationRepository(connection).update_tokens(
            authorization.id,
            access_token=cipher.encrypt(access_token.encode()).decode(),
            refresh_token=cipher.encrypt(new_refresh_token.encode()).decode(),
            api_server=token_data.get("api_server", authorization.api_server),
            access_expires_at=access_expires,
            refresh_expires_at=token_data.get(
                "refresh_token_expires_at", authorization.refresh_expires_at
            ),
        )
        connection.commit()

    def api_get(self, authorization: QuestradeAuthorization, path: str) -> dict[str, object]:
        url = self.validate_url(f"{authorization.api_server.rstrip('/')}{path}")
        cipher = self.cipher()
        token = cipher.decrypt(authorization.access_token.encode()).decode()
        try:
            # The URL is restricted to Questrade HTTPS hosts above.
            with urllib.request.urlopen(  # nosec B310
                urllib.request.Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "RetirementModel/1.0",
                    },
                ),
                timeout=30,
            ) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode(errors="replace").strip()
            finally:
                exc.close()
            message = f"Questrade API request failed ({exc.code})"
            if detail:
                message = f"{message}: {detail[:300]}"
            if exc.code == 401:
                raise QuestradeUnauthorized(message) from exc
            raise RuntimeError(message) from exc
        except (urllib.error.URLError, ValueError) as exc:
            raise RuntimeError(f"Questrade API request failed: {exc}") from exc

    def refresh_expiring_authorizations(self, connection: sqlite3.Connection) -> None:
        threshold = datetime.now(UTC) + timedelta(minutes=2)
        for authorization in QuestradeAuthorizationRepository(connection).list_all():
            expires_at = authorization.access_expires_at
            if not expires_at:
                continue
            try:
                expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if expires <= threshold:
                self.refresh_authorization(connection, authorization)
