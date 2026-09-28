from __future__ import annotations

from collections.abc import Callable
from sqlite3 import Connection

from infrastructure.migrations.baseline_domain_schema import BaselineDomainSchemaMigration
from infrastructure.migrations.migration_runner import MigrationRunner
from infrastructure.migrations.monetary_cents import MonetaryCentsMigration
from infrastructure.migrations.questrade_activity_identity import (
    QuestradeActivityIdentityMigration,
)
from infrastructure.migrations.questrade_sync_status import QuestradeSyncStatusMigration
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from services.csv_import_service import CsvImportService
from services.imported_transaction_repair import ImportedTransactionRepair
from services.legacy_fixed_deposit_migration import LegacyFixedDepositMigration
from services.transaction_service import TransactionService


def ensure_domain_schema(connection: Connection) -> None:
    MigrationRunner(
        connection,
        (
            BaselineDomainSchemaMigration(LegacyFixedDepositMigration(connection).execute),
            QuestradeSyncStatusMigration(),
            MonetaryCentsMigration(),
            QuestradeActivityIdentityMigration(),
        ),
    ).apply()


def initialize_database(connect: Callable[[], Connection]) -> None:
    """Apply schema and data repairs required when a runtime starts."""
    with connect() as connection:
        ensure_domain_schema(connection)
        ImportedTransactionRepair(connection).execute()
        CsvImportService(connection).repair_legacy_dates()
        transactions = TransactionService(connection)
        for account_id in AccountRepository(connection).list_ids():
            transactions.recalculate_balances(account_id)
        BalanceSnapshotRepository(connection).normalize_percentage_rates()
