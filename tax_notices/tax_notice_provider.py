# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from domain.parsed_tax_assessment import ParsedTaxAssessment

TaxNoticeParser = Callable[[bytes], ParsedTaxAssessment]
TaxNoticeDetector = Callable[[bytes], bool]


@dataclass(frozen=True, slots=True)
class TaxNoticeProvider:
    """Contract implemented by one government assessment-notice source."""

    key: str
    display_name: str
    source_label: str
    parser: TaxNoticeParser
    detects: TaxNoticeDetector
    help_text: str
    version: str = "2026.09.29.1"
