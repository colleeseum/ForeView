# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Locale-independent validation identity with backward-compatible diagnostic text."""


class ValidationError(ValueError):
    def __init__(self, code: str, message: str, **values: object) -> None:
        super().__init__(message)
        self.code = code
        self.values = values
