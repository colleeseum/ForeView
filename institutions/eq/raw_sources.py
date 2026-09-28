"""Source tags stored with raw rows imported from eq documents.

Rows with these tags carry the balance printed on the statement in their
``balance`` field. The values are persisted, so they must never change.
"""

EQ_PDF = "eq_pdf"

STATEMENT_SOURCES = (EQ_PDF,)
