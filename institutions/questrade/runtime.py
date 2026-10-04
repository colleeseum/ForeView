# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Build the Questrade connection adapter for the running application."""

from __future__ import annotations

from institution_support.runtime_context import RuntimeContext

from .client import QuestradeClient
from .connection import QuestradeConnectionProvider
from .settings import QuestradeSettings
from .sync import sync_questrade_connection


def create_connection_provider(runtime: RuntimeContext) -> QuestradeConnectionProvider:
    settings = QuestradeSettings.from_runtime(runtime)
    client = QuestradeClient(settings)

    def synchronize(connection_name: str, fetch_from: str | None = None) -> dict[str, object]:
        return sync_questrade_connection(
            runtime.connect,
            connection_name,
            api_getter=client.api_get,
            refresh_expiring=client.refresh_expiring_authorizations,
            refresh_authorization=client.refresh_authorization,
            history_start=settings.profiles.get(connection_name, {}).get("history_start"),
            fetch_from=fetch_from,
        )

    return QuestradeConnectionProvider(settings, runtime.connect, client, synchronize)
