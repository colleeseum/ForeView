"""Source tags stored with raw rows imported from achieva documents.

Rows with these tags carry the balance printed on the statement in their
``balance`` field. The values are persisted, so they must never change.
"""

ACHIEVA_GIC_PDF = "achieva_gic_pdf"

STATEMENT_SOURCES = (ACHIEVA_GIC_PDF,)
