# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from .account_type_provider import AccountTypeProvider


def provider() -> AccountTypeProvider:
    return AccountTypeProvider(
        "rrsp", "RRSP", "tax_deferred_withdrawal", "restricted", supports_holdings=True
    )
