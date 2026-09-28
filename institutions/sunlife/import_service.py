"""Persistence workflows for Sun Life RRSP documents."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from ingestion.pdf_document import PdfOpener, pdf_page_texts
from ingestion.statement_import import account_digits, already_imported, content_hash
from ingestion.statement_row_writer import StatementRowWriter
from institutions.sunlife import raw_sources
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.investment_holding_repository import InvestmentHoldingRepository
from services.transaction_service import TransactionService

StatementParser = Callable[[Iterable[str], str], dict[str, Any]]


class SunLifeImportService:
    """Import Sun Life statement and transaction-history facts."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        statement_parser: StatementParser,
        history_parser: StatementParser,
        pdf_opener: PdfOpener,
        allow_reconciled: bool = False,
    ) -> None:
        self._connection = connection
        self._statement_parser = statement_parser
        self._history_parser = history_parser
        self._pdf_opener = pdf_opener
        self._accounts = AccountRepository(connection)
        self._batches = ImportBatchRepository(connection)
        self._holdings = InvestmentHoldingRepository(connection)
        self._rows = StatementRowWriter(connection, allow_reconciled=allow_reconciled)
        self._snapshots = BalanceSnapshotRepository(connection)

    def import_transaction_history(
        self, account_id: int, filename: str, content: bytes
    ) -> dict[str, int | float | str]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        if existing:
            return already_imported(existing)
        parsed = self._parse(self._history_parser, content, filename)
        self._validate_account(account_id, parsed["account_number"], filename)
        rows = parsed["rows"]
        with self._connection:
            batch_id = self._batches.create(account_id, filename, file_hash, len(rows)).id
            counts = self._rows.write(
                batch_id,
                account_id,
                rows,
                source=raw_sources.SUNLIFE_TRANSACTION_HISTORY_PDF,
                # Matched on type rather than description, as these importers always have.
                identity=("transaction_date", "amount", "transaction_type"),
            )
            self._batches.update_row_count(batch_id, counts.imported)
            TransactionService(self._connection).recalculate_balances(account_id)
        return {
            "batch_id": batch_id,
            "imported": counts.imported,
            "duplicates": counts.duplicates,
            "status": "imported",
            "document_type": "sunlife_transaction_history",
        }

    def import_rrsp_statement(
        self, account_id: int, filename: str, content: bytes
    ) -> dict[str, int | float | str]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        parsed = self._parse(self._statement_parser, content, filename)
        if existing:
            return already_imported(existing)
        self._validate_account(account_id, parsed["account_number"], filename)
        holdings = parsed.get("holdings", [])
        with self._connection:
            batch_id = self._batches.create(account_id, filename, file_hash).id
            self._snapshots.add(
                account_id,
                parsed["statement_end"],
                float(parsed["closing_value"]),
                source_sheet="Sun Life RRSP statement",
                source_address=parsed["statement_end"],
            )
            self._holdings.delete_for_account_date(account_id, parsed["statement_end"])
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
        return {
            "batch_id": batch_id,
            "imported": 0,
            "duplicates": 0,
            "status": "imported",
            "document_type": "sunlife_rrsp_statement",
            "closing_value": float(parsed["closing_value"]),
            "holdings": len(holdings),
        }

    def _parse(self, parser: StatementParser, content: bytes, filename: str) -> dict[str, Any]:
        return parser(pdf_page_texts(self._pdf_opener, content), filename)

    def _validate_account(self, account_id: int, parsed_number: object, filename: str) -> None:
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError("Account not found")
        if account_digits(account.account_number) != account_digits(parsed_number):
            raise ValueError(f"{filename} belongs to a different account")
