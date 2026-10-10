# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Questrade institution module."""

from institution_support.connection_capability import ConnectionCapability, ConnectionOperation
from institution_support.help_topic import HelpTopic
from institution_support.institution_provider import InstitutionProvider

from .connection import QuestradeConnectionProvider
from .routes import blueprint
from .runtime import create_connection_provider

__all__ = ["QuestradeConnectionProvider", "provider"]


def provider() -> InstitutionProvider:
    return InstitutionProvider(
        key="questrade",
        display_name="Questrade",
        holds_securities=True,
        connection=ConnectionCapability(
            operations=frozenset(
                {
                    ConnectionOperation.AUTHORIZE,
                    ConnectionOperation.REFRESH,
                    ConnectionOperation.SYNC,
                }
            ),
            status_path="/api/connections/questrade/status",
            connect_path="/api/connections/questrade/connect",
            sync_path="/api/connections/questrade/sync",
            callback_path="/connections/questrade/callback",
            create_provider=create_connection_provider,
            routes=blueprint,
        ),
        help_topics=(
            HelpTopic(
                "connection",
                "Questrade connection",
                "Authorize each Questrade login separately, then synchronize accounts, balances, positions, and activities.",
                category="connections",
                owning_page="/connections",
            ),
        ),
    )
