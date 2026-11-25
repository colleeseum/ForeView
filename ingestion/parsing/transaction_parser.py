# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from typing import Protocol

from ingestion.parsing.import_source import ImportSource
from ingestion.parsing.parse_context import ParseContext
from ingestion.parsing.parsed_transaction_document import ParsedTransactionDocument
from ingestion.parsing.parser_identity import ParserIdentity


class TransactionParser(Protocol):
    """Parse original bytes without repositories, runtime configuration or writes.

    Return None only for an unrecognized format so another parser may try it.
    Recognized but malformed input raises ValueError. Implementations must return
    their own identity and the supplied source, preserving occurrence order.
    Purity is an adapter obligation, not a sandbox provided by this Protocol.
    """

    @property
    def identity(self) -> ParserIdentity: ...

    def parse(
        self, source: ImportSource, *, context: ParseContext
    ) -> ParsedTransactionDocument | None: ...
