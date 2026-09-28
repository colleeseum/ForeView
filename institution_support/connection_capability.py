"""Declarative remote-connection capability of an institution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Blueprint

    from institution_support.connection_provider import ConnectionProvider
    from institution_support.runtime_context import RuntimeContext


class ConnectionOperation(StrEnum):
    """Operations a remote institution connection may expose."""

    AUTHORIZE = "authorize"
    REFRESH = "refresh"
    SYNC = "sync"


@dataclass(frozen=True)
class ConnectionCapability:
    """Declarative connection capability owned by an institution provider."""

    operations: frozenset[ConnectionOperation]
    status_path: str
    connect_path: str
    sync_path: str
    callback_path: str | None = None
    # Builds the runtime adapter for the current configuration and database.
    create_provider: Callable[[RuntimeContext], ConnectionProvider] | None = None
    # HTTP routes the application registers for this connection.
    routes: Blueprint | None = None
