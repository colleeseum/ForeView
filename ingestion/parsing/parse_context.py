# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParseContext:
    """Source-matching hints only; no stored account ID or creation approval.

    These hints do not establish account ownership or resolve a database account.
    Analysis must independently resolve and validate the parser's evidence.
    """

    institution: str | None = None
    account_number: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for value in (self.institution, self.account_number):
            if value is not None and not isinstance(value, str):
                raise TypeError("Parsing hints must be text or None")
