# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Manulife institution declaration."""

from institution_support.document_importer import DocumentImporter
from institution_support.help_topic import HelpTopic
from institution_support.institution_provider import InstitutionProvider

from . import document_importers, raw_sources
from .import_service import ManulifeImportService

__all__ = ["ManulifeImportService", "provider"]


def provider() -> InstitutionProvider:
    help_text = "Manulife Personal Plan RRSP progress and annual statements"
    return InstitutionProvider(
        key="manulife",
        display_name="Manulife",
        statement_sources=raw_sources.STATEMENT_SOURCES,
        holds_securities=True,
        importers=(
            DocumentImporter(
                "Manulife RRSP statement",
                "rrsp",
                document_importers.is_manulife_rrsp_pdf,
                document_importers.import_manulife_rrsp_pdf,
                "import_manulife_rrsp_pdf",
                help_text,
                account_number=document_importers.rrsp_account_number,
                account_type="rrsp",
            ),
        ),
        help_topics=(HelpTopic("imports", "Manulife imports", help_text),),
    )
