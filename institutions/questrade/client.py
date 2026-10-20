# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken

from domain.questrade_authorization import QuestradeAuthorization
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository

from .refresh_error import QuestradeRefreshError
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
        try:
            cipher = self.cipher()
            refresh_token = cipher.decrypt(authorization.refresh_token.encode()).decode()
            self.validate_url(self._settings.token_url)
        except (RuntimeError, InvalidToken, ValueError, UnicodeError) as exc:
            raise QuestradeRefreshError("questrade_refresh_invalid") from exc
        form = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
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
                try:
                    payload = json.loads(exc.read())
                except (ValueError, UnicodeError, OSError):
                    payload = None
            finally:
                exc.close()
            # A bare HTTP 400 is not evidence that the authorization expired.
            rejected = (
                exc.code in (400, 401)
                and isinstance(payload, dict)
                and payload.get("error") == "invalid_grant"
            )
            code = (
                "questrade_authorization_rejected"
                if rejected
                else (
                    "questrade_refresh_unavailable"
                    if exc.code == 429 or exc.code >= 500
                    else "questrade_refresh_rejected"
                )
            )
            raise QuestradeRefreshError(code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise QuestradeRefreshError("questrade_refresh_unavailable") from exc
        except (ValueError, UnicodeError) as exc:
            raise QuestradeRefreshError("questrade_refresh_invalid") from exc

        try:
            if not isinstance(token_data, dict):
                raise ValueError("Invalid token response")
            access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)
            if (
                not isinstance(access_token, str)
                or not access_token
                or not isinstance(new_refresh_token, str)
                or not new_refresh_token
            ):
                raise ValueError("Invalid tokens")
            lifetime = int(token_data.get("expires_in", 1800))
            if lifetime <= 0:
                raise ValueError("Invalid token lifetime")
            access_expires = (datetime.now(UTC) + timedelta(seconds=lifetime)).isoformat(
                timespec="seconds"
            )
            api_server = self.validate_url(token_data.get("api_server", authorization.api_server))
            refresh_expires = token_data.get(
                "refresh_token_expires_at", authorization.refresh_expires_at
            )
            if refresh_expires is not None and not isinstance(refresh_expires, str):
                raise ValueError("Invalid refresh expiry")
        except (ValueError, TypeError, OverflowError, RuntimeError, AttributeError) as exc:
            raise QuestradeRefreshError("questrade_refresh_invalid") from exc
        QuestradeAuthorizationRepository(connection).update_tokens(
            authorization.id,
            access_token=cipher.encrypt(access_token.encode()).decode(),
            refresh_token=cipher.encrypt(new_refresh_token.encode()).decode(),
            api_server=api_server,
            access_expires_at=access_expires,
            refresh_expires_at=refresh_expires,
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
            exc.close()
            message = f"Questrade API request failed ({exc.code})"
            if exc.code == 401:
                raise QuestradeUnauthorized(message) from exc
            raise RuntimeError(message) from exc
        except (urllib.error.URLError, ValueError) as exc:
            raise RuntimeError(
                "Questrade API request failed: service unavailable or invalid response"
            ) from exc

    def refresh_expiring_authorizations(
        self, connection: sqlite3.Connection, *, name: str | None = None
    ) -> None:
        threshold = datetime.now(UTC) + timedelta(minutes=2)
        for authorization in QuestradeAuthorizationRepository(connection).list_all():
            if name is not None and authorization.name != name:
                continue
            expires_at = authorization.access_expires_at
            if not expires_at:
                continue
            try:
                expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if expires.tzinfo is not None and expires <= threshold:
                self.refresh_authorization(connection, authorization)
