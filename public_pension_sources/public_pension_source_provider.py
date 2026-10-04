# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from domain.parsed_public_pension_statement import ParsedPublicPensionStatement

PublicPensionParser = Callable[[bytes], ParsedPublicPensionStatement]
PublicPensionDetector = Callable[[bytes], bool]


@dataclass(frozen=True, slots=True)
class PublicPensionSourceProvider:
    """Contract implemented by one official public-pension document source."""

    key: str
    display_name: str
    parser: PublicPensionParser
    detects: PublicPensionDetector
    help_text: str
    version: str = "2026.09.29"
