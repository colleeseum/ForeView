"""Import workflow for RBC GIC transaction-history documents."""

from __future__ import annotations

import io
import sqlite3
from collections.abc import Callable, Iterable
from typing import Any

from domain.account import Account
from domain.gic_terms import GicTerms
from ingestion.pdf_document import PdfDocument
from ingestion.statement_import import account_digits, already_imported, content_hash
from ingestion.statement_row_writer import StatementRowWriter
from institutions.rbc import raw_sources
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.import_batch_repository import ImportBatchRepository
from services.transaction_service import TransactionService

StatementParser = Callable[[Iterable[str], str], dict[str, Any]]
PdfOpener = Callable[[io.BytesIO], PdfDocument]


class RbcGicHistoryImportService:
    """Persist GIC and associated savings activity under an RBC TFSA."""

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
        self._batches = ImportBatchRepository(connection)
        self._rows = StatementRowWriter(connection, allow_reconciled=allow_reconciled)
        self._snapshots = BalanceSnapshotRepository(connection)

    def import_history(
        self, account_id: int, filename: str, content: bytes
    ) -> dict[str, int | float | str]:
        file_hash = content_hash(content)
        existing = self._batches.get_by_hash(file_hash)
        if existing:
            return already_imported(existing)
        pdf = self._pdf_opener(io.BytesIO(content))
        parsed = self._parser([page.extract_text() or "" for page in pdf.pages], filename)
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError("Account not found")
        account_id, parent_account_id = self._resolve_accounts(account, parsed)
        parent = self._accounts.get(parent_account_id)
        if parent is None or account_digits(parent.account_number) != account_digits(
            parsed["account_number"]
        ):
            raise ValueError(f"{filename} belongs to a different account")

        rows = parsed["rows"]
        savings_rows = parsed.get("savings_rows", [])
        with self._connection:
            batch_id = self._batches.create(account_id, filename, file_hash, len(rows)).id
            counts = self._rows.write(
                batch_id,
                account_id,
                rows,
                source=raw_sources.RBC_GIC_PDF,
                raw_fields={"account_id": account_id},
            ) + self._rows.write(
                batch_id,
                parent_account_id,
                savings_rows,
                source=raw_sources.RBC_GIC_PDF_CASH,
                row_offset=len(rows),
                raw_fields={"account_id": parent_account_id},
            )
            self._snapshots.add(
                account_id,
                parsed["statement_date"],
                self._required_float(parsed["closing_value"]),
                source_sheet="RBC GIC PDF",
                source_address=filename,
            )
            if parsed.get("savings_closing") is not None:
                self._snapshots.add(
                    parent_account_id,
                    parsed["statement_date"],
                    self._required_float(parsed["savings_closing"]),
                    source_sheet="RBC GIC PDF",
                    source_address=filename,
                )
            self._batches.update_row_count(batch_id, counts.imported)
            TransactionService(self._connection).recalculate_balances(account_id)
        return {
            "batch_id": batch_id,
            "imported": counts.imported,
            "duplicates": counts.duplicates,
            "status": "imported",
            "closing_value": self._required_float(parsed["closing_value"]),
            "document_type": "gic",
        }

    def _resolve_accounts(self, account: Account, parsed: dict[str, Any]) -> tuple[int, int]:
        if account.asset_kind == "gic" and account.parent_account_id is not None:
            return account.id, account.parent_account_id
        certificate = parsed.get("certificate") or ""
        matching_child = self._accounts.find_gic_child_by_certificate(account.id, certificate)
        if matching_child:
            return matching_child.id, account.id
        if not parsed.get("certificate"):
            raise ValueError("Could not identify the GIC certificate in this transaction history")
        child_id = self._accounts.create_gic_child(
            account,
            f"RBC GIC {parsed['certificate']}",
            GicTerms(
                account_number=f"gic:{account.id}:{parsed['certificate']}",
                principal=self._required_float(parsed["closing_value"]),
                redeemable=bool(parsed.get("redeemable")),
            ),
        )
        self._ownership.copy(account.id, child_id)
        return child_id, account.id

    @staticmethod
    def _required_float(value: object) -> float:
        if not isinstance(value, (int, float, str)):
            raise TypeError("RBC GIC numeric value has an invalid type")
        return float(value)
