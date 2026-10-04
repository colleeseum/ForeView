# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from .account_type_provider import AccountTypeProvider


def provider() -> AccountTypeProvider:
    return AccountTypeProvider("non_registered", "Non-registered", "taxable_growth", "liquid")
