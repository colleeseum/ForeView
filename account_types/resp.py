# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from .account_type_provider import AccountTypeProvider


def provider() -> AccountTypeProvider:
    return AccountTypeProvider(
        "resp",
        "RESP",
        "education_assistance_withdrawal",
        "restricted",
        supports_holdings=True,
        aliases=("Registered Education Savings Plan",),
    )
