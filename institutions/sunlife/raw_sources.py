"""Source tags stored with raw rows imported from sunlife documents.

Rows with these tags carry the balance printed on the statement in their
``balance`` field. The values are persisted, so they must never change.
"""

SUNLIFE_TRANSACTION_HISTORY_PDF = "sunlife_transaction_history_pdf"

STATEMENT_SOURCES = (SUNLIFE_TRANSACTION_HISTORY_PDF,)
