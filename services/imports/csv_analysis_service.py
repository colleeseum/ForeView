# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from collections import Counter

from domain.calendar_date import canonical_date_or_stored, parse_calendar_date
from ingestion.analysis.csv_document_analysis import CsvDocumentAnalysis
from ingestion.analysis.csv_row_analysis import CsvRowAnalysis
from ingestion.csv_format import digits
from ingestion.parsing.parsed_transaction_document import ParsedTransactionDocument
from repositories.csv_analysis_repository import CsvAnalysisRepository


class CsvAnalysisService:
    """Analyse one parsed CSV without invoking any writing importer or guard.

    Matching follows RecordedTransactionMatcher's occurrence policy, including
    independent keys for rows with and without printed balances. Newly proposed
    occurrences are not added to this file's starting ledger. This is deliberately
    not a multi-file shadow ledger or a complete balance/checkpoint effect plan.
    """

    def __init__(self, repository: CsvAnalysisRepository) -> None:
        self._repository = repository

    def analyse(self, account_id: int, document: ParsedTransactionDocument) -> CsvDocumentAnalysis:
        snapshot = self._repository.read(account_id, document.source.content_hash)
        source_account = document.account_number
        if source_account is not None and (
            not digits(source_account)
            or digits(source_account) != digits(snapshot.account.account_number)
        ):
            raise ValueError("Source account number does not match the selected account")
        if snapshot.existing_batch is not None:
            return CsvDocumentAnalysis(
                document, snapshot.account, snapshot.existing_batch, (), None
            )

        # New evidence uses canonical dates. Equivalent legacy ISO forms must
        # match that same day without rewriting the stored source date.
        counts: Counter[tuple[object, ...]] = Counter()
        for stored in snapshot.ledger:
            base = (
                canonical_date_or_stored(stored.transaction_date),
                stored.amount_cents,
                stored.description,
            )
            counts[base] += 1
            counts[(*base, stored.balance_after_cents)] += 1
        checkpoint_dates = [
            day
            for checkpoint in snapshot.checkpoints
            if (day := parse_calendar_date(checkpoint.reconciled_through)) is not None
        ]
        lock_date = max(checkpoint_dates, default=None)
        locked_through = lock_date.isoformat() if lock_date is not None else None
        decisions = []
        for row in document.rows:
            key: tuple[object, ...] = (row.transaction_date, row.amount_cents, row.description)
            if row.source_balance_cents is not None:
                key = (*key, row.source_balance_cents)
            duplicate = counts[key] > 0
            if duplicate:
                counts[key] -= 1
            enters = (
                not duplicate
                and locked_through is not None
                and row.transaction_date <= locked_through
            )
            decisions.append(CsvRowAnalysis(row, duplicate, enters))
        return CsvDocumentAnalysis(
            document, snapshot.account, None, tuple(decisions), locked_through
        )
