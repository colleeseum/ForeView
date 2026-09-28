"""Achieva institution declaration."""

from institution_support.document_importer import DocumentImporter
from institution_support.help_topic import HelpTopic
from institution_support.institution_provider import InstitutionProvider

from . import document_importers, raw_sources
from .import_service import AchievaImportService

__all__ = ["AchievaImportService", "provider"]


def provider() -> InstitutionProvider:
    help_text = "Achieva GIC statements"
    return InstitutionProvider(
        key="achieva",
        display_name="Achieva",
        statement_sources=raw_sources.STATEMENT_SOURCES,
        importers=(
            DocumentImporter(
                name="Achieva GIC PDF",
                document_type="gic",
                detects=document_importers.is_achieva_gic_pdf,
                importer=document_importers.import_achieva_gic_pdf,
                account_resolver="import_achieva_gic_pdf",
                help_text=help_text,
            ),
        ),
        help_topics=(HelpTopic("imports", "Achieva imports", help_text),),
    )
