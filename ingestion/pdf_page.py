# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Text access to one page of a PDF document."""

from __future__ import annotations

from typing import Protocol


class PdfPage(Protocol):
    def extract_text(self) -> str | None: ...
