# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""SQLite schema creation and compatibility upgrades."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

DOMAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    birth_date TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    name TEXT,
    account_number TEXT,
    account_type TEXT NOT NULL,
    institution TEXT,
    tax_treatment TEXT NOT NULL DEFAULT 'unspecified',
    current_interest_rate REAL,
    asset_kind TEXT NOT NULL DEFAULT 'account',
    parent_account_id INTEGER REFERENCES accounts(id),
    balance_includes_children INTEGER NOT NULL DEFAULT 0 CHECK(balance_includes_children IN (0, 1)),
    start_date TEXT,
    maturity_date TEXT,
    maturity_value REAL,
    maturity_value_cents INTEGER,
    principal REAL,
    principal_cents INTEGER,
    redeemable INTEGER NOT NULL DEFAULT 0 CHECK(redeemable IN (0, 1)),
    external_provider TEXT,
    external_account_id TEXT
);
CREATE TABLE IF NOT EXISTS account_owners (
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    person_id INTEGER NOT NULL REFERENCES people(id),
    ownership_share REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY(account_id, person_id),
    CHECK(ownership_share > 0 AND ownership_share <= 1)
);
CREATE TABLE IF NOT EXISTS balance_snapshots (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    snapshot_date TEXT NOT NULL,
    amount REAL NOT NULL,
    amount_cents INTEGER,
    contribution REAL,
    contribution_cents INTEGER,
    lock_date TEXT,
    maturity_date TEXT,
    interest_rate REAL,
    source_sheet TEXT NOT NULL,
    source_address TEXT NOT NULL,
    UNIQUE(account_id, snapshot_date, source_sheet, source_address)
);
CREATE INDEX IF NOT EXISTS idx_balance_snapshots_date
    ON balance_snapshots(snapshot_date);
CREATE TABLE IF NOT EXISTS fixed_term_deposits (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    name TEXT NOT NULL,
    principal REAL NOT NULL CHECK(principal >= 0),
    principal_cents INTEGER,
    interest_rate REAL NOT NULL CHECK(interest_rate >= 0),
    start_date TEXT NOT NULL,
    maturity_date TEXT NOT NULL,
    maturity_value REAL,
    maturity_value_cents INTEGER,
    source_filename TEXT,
    redeemable INTEGER NOT NULL DEFAULT 0 CHECK(redeemable IN (0, 1)),
    renewal_rule TEXT NOT NULL DEFAULT 'cash_at_maturity'
);
CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    baseline_date TEXT NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS scenario_assumptions (
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT,
    PRIMARY KEY(scenario_id, key)
);
CREATE TABLE IF NOT EXISTS public_rule_approvals (
    rule_set_id TEXT NOT NULL,
    content_hash TEXT NOT NULL CHECK(length(content_hash) = 64),
    approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(rule_set_id, content_hash)
);
CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS statement_reconciliations (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
    statement_start TEXT NOT NULL,
    statement_end TEXT NOT NULL,
    opening_balance REAL,
    opening_balance_cents INTEGER,
    closing_balance REAL,
    closing_balance_cents INTEGER,
    statement_deposits REAL,
    statement_deposits_cents INTEGER,
    statement_withdrawals REAL,
    statement_withdrawals_cents INTEGER,
    csv_transaction_count INTEGER NOT NULL DEFAULT 0,
    csv_net_change REAL,
    csv_net_change_cents INTEGER,
    difference REAL,
    difference_cents INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, statement_start, statement_end)
);
CREATE TABLE IF NOT EXISTS investment_holdings (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    valuation_date TEXT NOT NULL,
    asset_class TEXT,
    fund_code TEXT NOT NULL,
    fund_name TEXT NOT NULL,
    units REAL NOT NULL,
    unit_price REAL NOT NULL,
    market_value REAL NOT NULL,
    market_value_cents INTEGER,
    allocation_pct REAL,
    source_filename TEXT NOT NULL,
    UNIQUE(account_id, valuation_date, fund_code, source_filename)
);
CREATE INDEX IF NOT EXISTS idx_investment_holdings_account_date
    ON investment_holdings(account_id, valuation_date);
CREATE TABLE IF NOT EXISTS real_estate_assets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    property_type TEXT,
    description TEXT,
    estimated_value REAL NOT NULL CHECK(estimated_value >= 0),
    estimated_value_cents INTEGER,
    valuation_date TEXT NOT NULL,
    acb REAL CHECK(acb IS NULL OR acb >= 0),
    acb_cents INTEGER,
    ownership_share REAL NOT NULL DEFAULT 1.0 CHECK(ownership_share > 0 AND ownership_share <= 1),
    principal_residence INTEGER NOT NULL DEFAULT 0 CHECK(principal_residence IN (0, 1)),
    effective_tax_rate REAL CHECK(effective_tax_rate IS NULL OR (effective_tax_rate >= 0 AND effective_tax_rate <= 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS real_estate_projections (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES real_estate_assets(id) ON DELETE CASCADE,
    scenario_id INTEGER REFERENCES scenarios(id),
    projection_date TEXT NOT NULL,
    projected_value REAL NOT NULL CHECK(projected_value >= 0),
    projected_value_cents INTEGER,
    projected_acb REAL CHECK(projected_acb IS NULL OR projected_acb >= 0),
    projected_acb_cents INTEGER,
    effective_tax_rate REAL CHECK(effective_tax_rate IS NULL OR (effective_tax_rate >= 0 AND effective_tax_rate <= 1)),
    note TEXT,
    UNIQUE(asset_id, scenario_id, projection_date)
);
CREATE INDEX IF NOT EXISTS idx_real_estate_projections_asset_date
    ON real_estate_projections(asset_id, projection_date);
CREATE TABLE IF NOT EXISTS real_estate_owners (
    asset_id INTEGER NOT NULL REFERENCES real_estate_assets(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(id),
    ownership_share REAL NOT NULL,
    PRIMARY KEY(asset_id, person_id),
    CHECK(ownership_share > 0 AND ownership_share <= 1)
);
CREATE TABLE IF NOT EXISTS questrade_connections (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL UNIQUE DEFAULT 'questrade',
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    api_server TEXT NOT NULL,
    access_expires_at TEXT,
    refresh_expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS questrade_authorizations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    api_server TEXT NOT NULL,
    access_expires_at TEXT,
    refresh_expires_at TEXT,
    last_sync_attempt_at TEXT,
    last_sync_at TEXT,
    last_sync_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Ledger periods confirmed against a statement or a known balance.
CREATE TABLE IF NOT EXISTS reconciliation_checkpoints (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    period_start TEXT,
    reconciled_through TEXT NOT NULL,
    closing_balance REAL NOT NULL,
    closing_balance_cents INTEGER,
    net_change REAL NOT NULL,
    net_change_cents INTEGER,
    transaction_count INTEGER NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('reconciled', 'needs_review', 'superseded')),
    difference REAL,
    difference_cents INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- How far each connected account's activity has been fetched.
CREATE TABLE IF NOT EXISTS activity_sync_state (
    account_id INTEGER PRIMARY KEY REFERENCES accounts(id),
    synced_until TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS raw_transactions (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES import_batches(id),
    row_number INTEGER NOT NULL,
    row_hash TEXT NOT NULL,
    raw_data TEXT NOT NULL,
    UNIQUE(batch_id, row_number),
    UNIQUE(batch_id, row_hash)
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    raw_transaction_id INTEGER REFERENCES raw_transactions(id),
    transaction_date TEXT NOT NULL,
    amount REAL NOT NULL,
    amount_cents INTEGER,
    description TEXT,
    balance_after REAL,
    balance_after_cents INTEGER,
    category TEXT,
    transaction_type TEXT NOT NULL DEFAULT 'unclassified',
    UNIQUE(account_id, transaction_date, amount, description, raw_transaction_id)
);
CREATE INDEX IF NOT EXISTS idx_transactions_account_date
    ON transactions(account_id, transaction_date);
"""


class DomainSchemaManager:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        migrate_fixed_deposits: Callable[[], int],
    ) -> None:
        self._connection = connection
        self._migrate_fixed_deposits = migrate_fixed_deposits

    def ensure(self) -> None:
        self._connection.executescript(DOMAIN_SCHEMA)
        columns = self._columns("accounts")
        import_columns = self._columns("import_batches")
        person_columns = self._columns("people")
        if "birth_date" not in person_columns:
            self._connection.execute("ALTER TABLE people ADD COLUMN birth_date TEXT")
        if "institution" not in columns:
            self._connection.execute("ALTER TABLE accounts ADD COLUMN institution TEXT")
        if "account_number" not in columns:
            self._connection.execute("ALTER TABLE accounts ADD COLUMN account_number TEXT")
        if "tax_treatment" not in columns:
            self._connection.execute(
                "ALTER TABLE accounts ADD COLUMN tax_treatment TEXT NOT NULL DEFAULT 'unspecified'"
            )
        if "current_interest_rate" not in columns:
            self._connection.execute("ALTER TABLE accounts ADD COLUMN current_interest_rate REAL")
        for column, definition in (
            ("asset_kind", "TEXT NOT NULL DEFAULT 'account'"),
            ("parent_account_id", "INTEGER REFERENCES accounts(id)"),
            ("start_date", "TEXT"),
            ("maturity_date", "TEXT"),
            ("maturity_value", "REAL"),
            ("maturity_value_cents", "INTEGER"),
            ("principal", "REAL"),
            ("principal_cents", "INTEGER"),
            ("redeemable", "INTEGER NOT NULL DEFAULT 0"),
            ("external_provider", "TEXT"),
            ("external_account_id", "TEXT"),
            ("balance_includes_children", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if column not in columns:
                self._connection.execute(f"ALTER TABLE accounts ADD COLUMN {column} {definition}")
        deposit_columns = self._columns("fixed_term_deposits")
        if "maturity_value" not in deposit_columns:
            self._connection.execute(
                "ALTER TABLE fixed_term_deposits ADD COLUMN maturity_value REAL"
            )
        if "principal_cents" not in deposit_columns:
            self._connection.execute(
                "ALTER TABLE fixed_term_deposits ADD COLUMN principal_cents INTEGER"
            )
        if "maturity_value_cents" not in deposit_columns:
            self._connection.execute(
                "ALTER TABLE fixed_term_deposits ADD COLUMN maturity_value_cents INTEGER"
            )
        if "source_filename" not in deposit_columns:
            self._connection.execute(
                "ALTER TABLE fixed_term_deposits ADD COLUMN source_filename TEXT"
            )
        if "account_id" not in import_columns:
            self._connection.execute(
                "ALTER TABLE import_batches ADD COLUMN account_id INTEGER REFERENCES accounts(id)"
            )
        self._connection.execute(
            """
            UPDATE import_batches
            SET account_id = (
                SELECT t.account_id
                FROM raw_transactions r
                JOIN transactions t ON t.raw_transaction_id = r.id
                WHERE r.batch_id = import_batches.id
                ORDER BY t.id
                LIMIT 1
            )
            WHERE account_id IS NULL
            """
        )
        if "owner_id" in columns:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO account_owners(account_id, person_id, ownership_share)
                SELECT id, owner_id, 1.0 FROM accounts WHERE owner_id IS NOT NULL
                """
            )
        self._connection.execute(
            """UPDATE accounts
               SET maturity_value_cents = CAST(ROUND(maturity_value * 100) AS INTEGER)
               WHERE maturity_value IS NOT NULL AND maturity_value_cents IS NULL"""
        )
        self._connection.execute(
            """UPDATE accounts SET principal_cents = CAST(ROUND(principal * 100) AS INTEGER)
               WHERE principal IS NOT NULL AND principal_cents IS NULL"""
        )
        self._connection.execute(
            """UPDATE fixed_term_deposits
               SET principal_cents = CAST(ROUND(principal * 100) AS INTEGER)
               WHERE principal IS NOT NULL AND principal_cents IS NULL"""
        )
        self._connection.execute(
            """UPDATE fixed_term_deposits
               SET maturity_value_cents = CAST(ROUND(maturity_value * 100) AS INTEGER)
               WHERE maturity_value IS NOT NULL AND maturity_value_cents IS NULL"""
        )
        self._migrate_fixed_deposits()
        self._connection.commit()

    def _columns(self, table: str) -> set[str]:
        return {str(row[1]) for row in self._connection.execute(f"PRAGMA table_info({table})")}
