# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Safe refresh diagnostics, without upstream response bodies or credentials."""


class QuestradeRefreshError(RuntimeError):
    MESSAGES = {
        "questrade_authorization_rejected": "Questrade token refresh failed: authorization rejected. Reconnect this login.",
        "questrade_refresh_unavailable": "Questrade token refresh failed: service unavailable. Retry later.",
        "questrade_refresh_invalid": "Questrade token refresh failed: invalid response or configuration. Review this connection.",
        "questrade_refresh_rejected": "Questrade token refresh failed: request rejected. Review configuration or reconnect.",
    }

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(self.MESSAGES[code])
