# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Source tags stored with raw rows imported from manulife documents.

Rows with these tags carry the balance printed on the statement in their
``balance`` field. The values are persisted, so they must never change.
"""

MANULIFE_RRSP_PDF = "manulife_rrsp_pdf"

STATEMENT_SOURCES = (MANULIFE_RRSP_PDF,)
