# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Persistence workflow for Manulife RRSP statements."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from ingestion.pdf_document import PdfOpener, pdf_page_texts
from ingestion.statement_import import account_digits, already_imported, content_hash
from ingestion.statement_row_writer import StatementRowWriter
from institutions.manulife import raw_sources
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.investment_holding_repository import InvestmentHoldingRepository
from services.transaction_service import TransactionService

StatementParser = Callable[[Iterable[str], str], dict[str, Any]]


class ManulifeImportService:
    """Import Manulife statement facts without exposing them to the web layer."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        parser: StatementParser,
        pdf_opener: PdfOpener,
        allow_reconciled: bool = False,
    ) -> None:
        self._connection = connection
        self._parser = parser
        self._pdf_opener = pdf_opener
        self._accounts = AccountRepository(connection)
        self._batches = ImportBatchRepository(connection)
        self._holdings = InvestmentHoldingRepository(connection)
        self._rows = StatementRowWriter(connection, allow_reconciled=allow_reconciled)
        self._snapshots = BalanceSnapshotRepository(connection)

    def import_rrsp(
        self, account_id: int, filename: str, content: bytes
    ) -> dict[str, int | float | str]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        parsed = self._parse(content, filename)
        if existing:
            if existing.account_id and parsed.get("holdings"):
                with self._connection:
                    self._store_holdings(existing.account_id, filename, parsed["holdings"])
            return already_imported(existing)

        self._validate_account(account_id, parsed["account_number"], filename)

        rows = parsed["rows"]
        with self._connection:
            batch_id = self._batches.create(account_id, filename, file_hash, len(rows)).id
            counts = self._rows.write(
                batch_id,
                account_id,
                rows,
                source=raw_sources.MANULIFE_RRSP_PDF,
                # Matched on type rather than description, as these importers always have.
                identity=("transaction_date", "amount", "transaction_type"),
            )
            self._store_statement_snapshots(account_id, filename, parsed)
            self._store_holdings(account_id, filename, parsed.get("holdings", []))
            self._batches.update_row_count(batch_id, counts.imported)
            TransactionService(self._connection).recalculate_balances(account_id)
        return {
            "batch_id": batch_id,
            "imported": counts.imported,
            "duplicates": counts.duplicates,
            "status": "imported",
            "document_type": "manulife_rrsp",
            "closing_value": float(parsed["closing_value"]),
        }

    def _parse(self, content: bytes, filename: str) -> dict[str, Any]:
        return self._parser(pdf_page_texts(self._pdf_opener, content), filename)

    def _validate_account(self, account_id: int, parsed_number: object, filename: str) -> None:
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError("Account not found")
        if account_digits(account.account_number) != account_digits(parsed_number):
            raise ValueError(f"{filename} belongs to a different account")

    def _store_statement_snapshots(
        self, account_id: int, filename: str, parsed: dict[str, Any]
    ) -> None:
        self._snapshots.add(
            account_id,
            parsed["statement_start"],
            float(parsed["opening_value"]),
            source_sheet="Manulife RRSP PDF",
            source_address=filename,
        )
        self._snapshots.add(
            account_id,
            parsed["statement_end"],
            float(parsed["closing_value"]),
            source_sheet="Manulife RRSP PDF",
            source_address=filename,
        )

    def _store_holdings(
        self, account_id: int, filename: str, holdings: Iterable[dict[str, Any]]
    ) -> None:
        for holding in holdings:
            self._holdings.upsert(
                account_id,
                holding["valuation_date"],
                holding["asset_class"],
                holding["fund_code"],
                holding["fund_name"],
                holding["units"],
                holding["unit_price"],
                holding["market_value"],
                holding["allocation_pct"],
                filename,
            )
