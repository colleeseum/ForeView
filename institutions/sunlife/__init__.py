# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Sun Life institution declaration."""

from institution_support.document_importer import DocumentImporter
from institution_support.help_topic import HelpTopic
from institution_support.institution_provider import InstitutionProvider

from . import document_importers, raw_sources
from .import_service import SunLifeImportService

__all__ = ["SunLifeImportService", "provider"]


def provider() -> InstitutionProvider:
    importers = (
        DocumentImporter(
            "Sun Life RRSP statement",
            "rrsp",
            document_importers.is_sunlife_rrsp_pdf,
            document_importers.import_sunlife_rrsp_pdf,
            "import_sunlife_rrsp_pdf",
            "Sun Life Group Choices RRSP statements with balances and holdings",
            account_number=document_importers.rrsp_account_number,
            account_type="rrsp",
        ),
        DocumentImporter(
            "Sun Life transaction history",
            "rrsp",
            document_importers.is_sunlife_transaction_history_pdf,
            document_importers.import_sunlife_transaction_history_pdf,
            "import_sunlife_transaction_history_pdf",
            "Sun Life Group Choices transaction-history PDFs",
            account_number=document_importers.transaction_history_account_number,
            account_type="rrsp",
        ),
    )
    return InstitutionProvider(
        key="sunlife",
        display_name="Sun Life",
        statement_sources=raw_sources.STATEMENT_SOURCES,
        holds_securities=True,
        aliases=("Sunlife",),
        importers=importers,
        help_topics=(
            HelpTopic(
                "imports",
                "Sun Life imports",
                "Sun Life Group Choices RRSP statements and transaction histories.",
            ),
        ),
    )
