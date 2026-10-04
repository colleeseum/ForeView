# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0


class PublicRuleUpdateError(RuntimeError):
    """Base error for retrieval, parsing, and package generation failures."""


class RuleRetrievalError(PublicRuleUpdateError):
    """An official source could not be retrieved safely."""


class RuleSourceFormatError(PublicRuleUpdateError):
    """An official source no longer matches the expected structure."""
