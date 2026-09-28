"""RBC institution declaration."""

from institution_support.document_importer import DocumentImporter
from institution_support.help_topic import HelpTopic
from institution_support.institution_provider import InstitutionProvider

from . import csv_parser, document_importers, raw_sources, transaction_repair
from .deposit_import_service import RbcDepositImportService
from .gic_history_import_service import RbcGicHistoryImportService
from .tfsa_import_service import RbcTfsaImportService

__all__ = [
    "RbcDepositImportService",
    "RbcGicHistoryImportService",
    "RbcTfsaImportService",
    "provider",
]


def provider() -> InstitutionProvider:
    importers = (
        DocumentImporter(
            "RBC GIC transaction history",
            "gic",
            document_importers.is_rbc_gic_transaction_history_pdf,
            document_importers.import_rbc_gic_transaction_history_pdf,
            "import_rbc_gic_transaction_history_pdf",
            "RBC online-banking GIC transaction history PDFs",
            account_number=document_importers.gic_history_account_number,
            account_type="tfsa",
        ),
        DocumentImporter(
            "RBC TFSA statement",
            "tfsa",
            document_importers.is_rbc_tfsa_pdf,
            document_importers.import_rbc_tfsa_pdf,
            "import_rbc_tfsa_pdf",
            "RBC TFSA investment statements and CPG maturity notices",
            account_number=document_importers.tfsa_account_number,
            account_type="tfsa",
        ),
        DocumentImporter(
            "RBC deposit statement",
            "account",
            document_importers.is_rbc_statement_pdf,
            document_importers.import_rbc_statement_pdf,
            "import_rbc_statement_pdf",
            "RBC personal deposit statements",
            account_number=document_importers.deposit_account_number,
            account_type="non_registered",
        ),
    )
    return InstitutionProvider(
        key="rbc",
        display_name="RBC",
        statement_sources=raw_sources.STATEMENT_SOURCES,
        csv_parser=csv_parser.parse_transactions,
        balance_excluded_sources=(raw_sources.RBC_TFSA_PDF,),
        balance_including_snapshot_sources=("RBC TFSA PDF",),
        transaction_repair=transaction_repair.repair_transactions,
        aliases=("Royal Bank", "Royal Bank of Canada"),
        importers=importers,
        help_topics=(
            HelpTopic(
                "imports",
                "RBC imports",
                "RBC deposit statements, TFSA investment statements, GIC transaction "
                "histories, and CPG maturity notices.",
            ),
        ),
    )
