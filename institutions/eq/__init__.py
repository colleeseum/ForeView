# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""EQ Bank institution declaration."""

from institution_support.help_topic import HelpTopic
from institution_support.institution_provider import InstitutionProvider

from . import raw_sources, transaction_repair
from .import_service import EqImportService

__all__ = ["EqImportService", "provider"]


def provider() -> InstitutionProvider:
    return InstitutionProvider(
        key="eq",
        display_name="EQ Bank",
        statement_sources=raw_sources.STATEMENT_SOURCES,
        transaction_repair=transaction_repair.repair_transactions,
        aliases=("EQ",),
        help_topics=(
            HelpTopic(
                "imports",
                "EQ Bank imports",
                "EQ Bank monthly statements are supported when importing into an existing account.",
            ),
        ),
    )
