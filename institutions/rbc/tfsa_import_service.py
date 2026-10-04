# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Import workflow for RBC TFSA statements and GIC maturity notices."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from domain.gic_terms import GicTerms
from ingestion.pdf_document import PdfOpener, pdf_page_texts
from ingestion.statement_import import (
    account_digits,
    already_imported,
    content_hash,
    unrecognized_pdf,
)
from ingestion.statement_row_writer import StatementRowWriter
from institutions.rbc import raw_sources
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.fixed_term_deposit_repository import FixedTermDepositRepository
from repositories.import_batch_repository import ImportBatchRepository
from services.transaction_service import TransactionService

StatementParser = Callable[[Iterable[str], str], dict[str, Any]]

# Savings events on TFSA statements are interest; the statement prints no running balance.
INTEREST_EVENT = {"balance": None, "category": "Interest", "transaction_type": "interest"}


class RbcTfsaImportService:
    """Persist RBC TFSA cash activity and linked GIC facts."""

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
        self._ownership = AccountOwnershipRepository(connection)
        self._snapshots = BalanceSnapshotRepository(connection)
        self._deposits = FixedTermDepositRepository(connection)
        self._batches = ImportBatchRepository(connection)
        self._rows = StatementRowWriter(connection, allow_reconciled=allow_reconciled)

    def import_document(
        self, account_id: int, filename: str, content: bytes
    ) -> dict[str, int | float | str | None]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        if existing:
            return already_imported(existing)
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError("Account not found")
        parsed = self._parse(content, filename, account.institution or "RBC")
        if account_digits(parsed["account_number"]) != account_digits(account.account_number):
            raise ValueError(f"{filename} belongs to a different account")

        events = list(parsed.get("savings_events", []))
        with self._connection:
            batch_id = self._batches.create(account_id, filename, file_hash, len(events)).id
            imported = self._rows.write(
                batch_id,
                account_id,
                events,
                source=raw_sources.RBC_TFSA_PDF,
                transaction_fields=INTEREST_EVENT,
            ).imported
            if parsed["document_type"] == "statement":
                self._store_parent_balance(account_id, filename, parsed)
            gics = parsed["gics"]
            for gic in gics:
                gic["snapshot_date"] = parsed.get("statement_end")
                self.upsert_gic(account_id, gic, filename)
            self._batches.update_row_count(batch_id, imported)
            TransactionService(self._connection).recalculate_balances(account_id)
        return {
            "batch_id": batch_id,
            "imported": imported,
            "duplicates": len(events) - imported,
            "status": "imported",
            "document_type": parsed["document_type"],
            "gics": len(gics),
            "closing_value": parsed.get("closing_value"),
        }

    def upsert_gic(self, account_id: int, gic: dict[str, object], filename: str) -> int:
        name = f"RBC CPG {gic['certificate']}"
        principal = self._required_float(gic["principal"])
        interest_rate = self._required_float(gic["interest_rate"])
        deposit_id = self._deposits.upsert_imported(
            account_id,
            name,
            principal,
            interest_rate,
            str(gic["start_date"]),
            str(gic["maturity_date"]),
            maturity_value=self._optional_float(gic.get("maturity_value")),
            source_filename=filename,
            redeemable=bool(gic.get("redeemable", False)),
        ).id
        parent = self._accounts.get(account_id)
        if parent is None:
            raise ValueError("Account not found")
        child = self._accounts.find_gic_child(
            account_id,
            name=name,
            certificate_pattern=f"%{gic['certificate']}%",
            principal=principal,
            start_date=str(gic["start_date"]),
        )
        account_number = f"gic:{account_id}:{gic['certificate']}"
        terms = GicTerms(
            account_number=account_number,
            interest_rate=interest_rate,
            start_date=str(gic["start_date"]),
            maturity_date=str(gic["maturity_date"]),
            maturity_value=self._optional_float(gic.get("maturity_value")),
            principal=principal,
            redeemable=bool(gic.get("redeemable", False)),
        )
        if child:
            child_id = child.id
            self._accounts.update_gic_child(child_id, parent, terms)
        else:
            child_id = self._accounts.create_gic_child(parent, name, terms)
            self._ownership.copy(account_id, child_id)
        if gic.get("value_at_statement") is not None:
            self._snapshots.add(
                child_id,
                str(gic.get("snapshot_date") or gic["maturity_date"]),
                self._required_float(gic["value_at_statement"]),
                interest_rate,
                lock_date=str(gic["start_date"]),
                maturity_date=str(gic["maturity_date"]),
                source_sheet="RBC TFSA PDF",
                source_address=filename,
            )
        return deposit_id

    def _parse(self, content: bytes, filename: str, institution: str) -> dict[str, Any]:
        try:
            return self._parser(pdf_page_texts(self._pdf_opener, content), filename)
        except ValueError as error:
            raise unrecognized_pdf(institution) from error

    def _store_parent_balance(self, account_id: int, filename: str, parsed: dict[str, Any]) -> None:
        parent_amount = parsed.get("savings_closing")
        self._accounts.set_balance_includes_children(account_id, parent_amount is None)
        self._snapshots.add(
            account_id,
            parsed["statement_end"],
            float(parent_amount if parent_amount is not None else parsed["closing_value"]),
            source_sheet="RBC TFSA PDF",
            source_address=filename,
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return RbcTfsaImportService._required_float(value) if value is not None else None

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("RBC GIC numeric value has an invalid type")
        return float(value)
