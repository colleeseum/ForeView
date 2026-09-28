"""Source tags stored with raw rows imported from rbc documents.

Rows with these tags carry the balance printed on the statement in their
``balance`` field. The values are persisted, so they must never change.
"""

RBC_GIC_PDF = "rbc_gic_pdf"
RBC_GIC_PDF_CASH = "rbc_gic_pdf_cash"
RBC_TFSA_PDF = "rbc_tfsa_pdf"

STATEMENT_SOURCES = (
    RBC_GIC_PDF,
    RBC_GIC_PDF_CASH,
    RBC_TFSA_PDF,
)
