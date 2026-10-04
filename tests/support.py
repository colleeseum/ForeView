# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Test setup adapters retained while repository parity coverage is simplified."""

from __future__ import annotations

import sqlite3

import pdfplumber  # noqa: F401 - compatibility name for PDF importer tests

from domain.money import MoneyInput
from institution_support.registry import institution_registry
from institutions.achieva.document_importers import import_achieva_gic_pdf, is_achieva_gic_pdf
from institutions.eq.document_importers import import_eq_statement_pdf
from institutions.eq.parser import parse_eq_pdf_transactions
from institutions.manulife.document_importers import (
    import_manulife_rrsp_pdf,
    is_manulife_rrsp_pdf,
)
from institutions.rbc.document_importers import (
    import_rbc_gic_transaction_history_pdf,
    import_rbc_statement_pdf,
    import_rbc_tfsa_pdf,
    is_rbc_gic_transaction_history_pdf,
    is_rbc_statement_pdf,
    is_rbc_tfsa_pdf,
    parse_rbc_statement_summary,
    upsert_imported_gic,
)
from institutions.rbc.parser import (
    parse_gic_transaction_history as parse_rbc_gic_transaction_history,
)
from institutions.rbc.parser import (
    parse_tfsa_statement as parse_rbc_tfsa_statement,
)
from institutions.sunlife.document_importers import (
    import_sunlife_rrsp_pdf,
    import_sunlife_transaction_history_pdf,
    is_sunlife_rrsp_pdf,
    is_sunlife_transaction_history_pdf,
)
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.fixed_term_deposit_repository import FixedTermDepositRepository
from repositories.import_batch_repository import ImportBatchRepository
from repositories.investment_holding_repository import InvestmentHoldingRepository
from repositories.person_repository import PersonRepository
from repositories.real_estate_asset_repository import RealEstateAssetRepository
from repositories.real_estate_ownership_repository import RealEstateOwnershipRepository
from repositories.real_estate_projection_repository import RealEstateProjectionRepository
from repositories.scenario_assumption_repository import ScenarioAssumptionRepository
from repositories.scenario_repository import ScenarioRepository
from services.account_aggregation_service import AccountAggregationService
from services.account_summary_query import AccountSummaryQuery
from services.csv_import_service import CsvImportService
from services.database_initialization import ensure_domain_schema
from services.document_import_account_resolver import DocumentImportAccountResolver
from services.imported_transaction_repair import ImportedTransactionRepair
from services.legacy_fixed_deposit_migration import LegacyFixedDepositMigration
from services.real_estate_summary_query import RealEstateSummaryQuery
from services.transaction_service import TransactionService

__all__ = [
    "ensure_domain_schema",
    "import_achieva_gic_pdf",
    "import_manulife_rrsp_pdf",
    "import_rbc_gic_transaction_history_pdf",
    "import_rbc_statement_pdf",
    "import_rbc_tfsa_pdf",
    "import_sunlife_rrsp_pdf",
    "import_sunlife_transaction_history_pdf",
    "is_achieva_gic_pdf",
    "is_manulife_rrsp_pdf",
    "is_rbc_gic_transaction_history_pdf",
    "is_rbc_statement_pdf",
    "is_rbc_tfsa_pdf",
    "is_sunlife_rrsp_pdf",
    "is_sunlife_transaction_history_pdf",
    "parse_eq_pdf_transactions",
    "parse_rbc_gic_transaction_history",
    "parse_rbc_statement_summary",
    "parse_rbc_tfsa_statement",
]


def _person_id(connection: sqlite3.Connection, name: str | None) -> int | None:
    person = PersonRepository(connection).find_or_create(name)
    return person.id if person else None


def create_person(connection: sqlite3.Connection, name: str, birth_date: str | None = None) -> int:
    return PersonRepository(connection).create(name, birth_date).id


def update_person_birth_date(
    connection: sqlite3.Connection, person_id: int, birth_date: str
) -> None:
    PersonRepository(connection).update_birth_date(person_id, birth_date)


def migrate_legacy_fixed_deposits(connection: sqlite3.Connection) -> int:
    return LegacyFixedDepositMigration(connection).execute()


def create_account(
    connection: sqlite3.Connection,
    name: str | None,
    account_type: str,
    *,
    account_number: str,
    institution: str | None = None,
    tax_treatment: str | None = None,
    asset_kind: str = "account",
    external_provider: str | None = None,
    external_account_id: str | None = None,
    parent_account_id: int | None = None,
    start_date: str | None = None,
    maturity_date: str | None = None,
    maturity_value: MoneyInput | None = None,
    principal: MoneyInput | None = None,
    redeemable: bool = False,
) -> int:
    return (
        AccountRepository(connection)
        .create(
            name,
            account_type,
            account_number=account_number,
            institution=institution,
            tax_treatment=tax_treatment,
            asset_kind=asset_kind,
            external_provider=external_provider,
            external_account_id=external_account_id,
            parent_account_id=parent_account_id,
            start_date=start_date,
            maturity_date=maturity_date,
            maturity_value=maturity_value,
            principal=principal,
            redeemable=redeemable,
        )
        .id
    )


def update_account(
    connection: sqlite3.Connection,
    account_id: int,
    *,
    name: str | None,
    account_number: str,
    institution: str | None,
    category: str | None = None,
    asset_kind: str | None = None,
    external_provider: str | None = None,
    external_account_id: str | None = None,
    parent_account_id: int | None = None,
    start_date: str | None = None,
    maturity_date: str | None = None,
    maturity_value: MoneyInput | None = None,
    principal: MoneyInput | None = None,
    redeemable: bool = False,
) -> None:
    AccountRepository(connection).update(
        account_id,
        name=name,
        account_number=account_number,
        institution=institution,
        category=category,
        asset_kind=asset_kind,
        external_provider=external_provider,
        external_account_id=external_account_id,
        parent_account_id=parent_account_id,
        start_date=start_date,
        maturity_date=maturity_date,
        maturity_value=maturity_value,
        principal=principal,
        redeemable=redeemable,
    )


def create_real_estate_asset(
    connection: sqlite3.Connection,
    name: str,
    estimated_value: MoneyInput,
    valuation_date: str,
    *,
    property_type: str | None = None,
    description: str | None = None,
    acb: MoneyInput | None = None,
    ownership_share: float = 1.0,
    principal_residence: bool = False,
    effective_tax_rate: float | None = None,
) -> int:
    return (
        RealEstateAssetRepository(connection)
        .create(
            name,
            estimated_value,
            valuation_date,
            property_type=property_type,
            description=description,
            acb=acb,
            ownership_share=ownership_share,
            principal_residence=principal_residence,
            effective_tax_rate=effective_tax_rate,
        )
        .id
    )


def set_real_estate_owners(
    connection: sqlite3.Connection, asset_id: int, owners: list[tuple[int, float]]
) -> None:
    RealEstateOwnershipRepository(connection).replace(asset_id, owners)


def update_real_estate_asset(
    connection: sqlite3.Connection,
    asset_id: int,
    name: str,
    estimated_value: MoneyInput,
    valuation_date: str,
    *,
    property_type: str | None = None,
    description: str | None = None,
    acb: MoneyInput | None = None,
    ownership_share: float = 1.0,
    principal_residence: bool = False,
    effective_tax_rate: float | None = None,
) -> None:
    RealEstateAssetRepository(connection).update(
        asset_id,
        name,
        estimated_value,
        valuation_date,
        property_type=property_type,
        description=description,
        acb=acb,
        ownership_share=ownership_share,
        principal_residence=principal_residence,
        effective_tax_rate=effective_tax_rate,
    )


def add_real_estate_projection(
    connection: sqlite3.Connection,
    asset_id: int,
    projection_date: str,
    projected_value: MoneyInput,
    *,
    scenario_id: int | None = None,
    projected_acb: MoneyInput | None = None,
    effective_tax_rate: float | None = None,
    note: str | None = None,
) -> int:
    return (
        RealEstateProjectionRepository(connection)
        .create(
            asset_id,
            projection_date,
            projected_value,
            scenario_id=scenario_id,
            projected_acb=projected_acb,
            effective_tax_rate=effective_tax_rate,
            note=note,
        )
        .id
    )


def real_estate_summary(connection: sqlite3.Connection) -> list[dict[str, object]]:
    return RealEstateSummaryQuery(connection).execute()


def set_account_current_interest_rate(
    connection: sqlite3.Connection, account_id: int, interest_rate: float | None
) -> None:
    AccountRepository(connection).set_current_interest_rate(account_id, interest_rate)


def add_balance_snapshot(
    connection: sqlite3.Connection,
    account_id: int,
    snapshot_date: str,
    amount: MoneyInput,
    interest_rate: float | None = None,
    *,
    source_sheet: str = "application",
    source_address: str = "manual",
) -> None:
    BalanceSnapshotRepository(connection).add(
        account_id,
        snapshot_date,
        amount,
        interest_rate,
        source_sheet=source_sheet,
        source_address=source_address,
    )


def recalculate_transaction_balances(connection: sqlite3.Connection, account_id: int) -> int:
    return TransactionService(connection).recalculate_balances(account_id)


def repair_imported_csv_dates(connection: sqlite3.Connection) -> int:
    return CsvImportService(connection).repair_legacy_dates()


def resolve_import_account(
    connection: sqlite3.Connection, importer_name: str, content: bytes, filename: str
) -> int:
    """Find or create a parent account when a supported PDF identifies it."""
    return DocumentImportAccountResolver(connection, institution_registry()).resolve(
        importer_name, content, filename
    )


def _upsert_imported_gic(
    connection: sqlite3.Connection, account_id: int, gic: dict[str, object], filename: str
) -> int:
    return upsert_imported_gic(connection, account_id, gic, filename)


def import_csv_transactions(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | str]:
    return CsvImportService(connection).import_transactions(
        account_id, filename, content, allow_reconciled=allow_reconciled
    )


def repair_imported_pdf_descriptions(connection: sqlite3.Connection) -> int:
    """Backfill descriptions for EQ rows imported by the original parser."""
    return ImportedTransactionRepair(connection).execute()


def import_pdf_transactions(
    connection: sqlite3.Connection,
    account_id: int,
    filename: str,
    content: bytes,
    *,
    allow_reconciled: bool = False,
) -> dict[str, int | str]:
    return import_eq_statement_pdf(
        connection, account_id, filename, content, allow_reconciled=allow_reconciled
    )


def set_account_owners(
    connection: sqlite3.Connection, account_id: int, owners: list[tuple[int, float]]
) -> None:
    AccountOwnershipRepository(connection).replace(account_id, owners)


def add_fixed_term_deposit(
    connection: sqlite3.Connection,
    account_id: int,
    name: str,
    principal: MoneyInput,
    interest_rate: float,
    start_date: str,
    maturity_date: str,
    *,
    redeemable: bool = False,
    renewal_rule: str = "cash_at_maturity",
    maturity_value: MoneyInput | None = None,
    source_filename: str | None = None,
) -> int:
    return (
        FixedTermDepositRepository(connection)
        .create(
            account_id,
            name,
            principal,
            interest_rate,
            start_date,
            maturity_date,
            redeemable=redeemable,
            renewal_rule=renewal_rule,
            maturity_value=maturity_value,
            source_filename=source_filename,
        )
        .id
    )


def create_scenario(
    connection: sqlite3.Connection, name: str, baseline_date: str, description: str | None = None
) -> int:
    return ScenarioRepository(connection).create(name, baseline_date, description).id


def set_scenario_assumption(
    connection: sqlite3.Connection, scenario_id: int, key: str, value: str, unit: str | None = None
) -> None:
    ScenarioAssumptionRepository(connection).set(scenario_id, key, value, unit)


def account_summary(connection: sqlite3.Connection) -> list[dict[str, object]]:
    return AccountSummaryQuery(connection).execute()


def account_category_totals(accounts: list[dict[str, object]]) -> list[dict[str, object]]:
    """Calculate category totals without double-counting consolidated children."""
    return AccountAggregationService().category_totals(accounts)


def investment_holdings_summary(
    connection: sqlite3.Connection, account_id: int | None = None, account_type: str | None = None
) -> list[dict[str, object]]:
    return InvestmentHoldingRepository(connection).latest(account_id, account_type)


def annual_summary(connection: sqlite3.Connection) -> list[dict[str, object]]:
    return BalanceSnapshotRepository(connection).annual_totals()


def transaction_summary(
    connection: sqlite3.Connection,
    account_id: int | None = None,
    account_type: str | None = None,
    limit: int = 250,
) -> list[dict[str, object]]:
    return TransactionService(connection).summary(account_id, account_type, limit)


def transaction_opening_balances(
    connection: sqlite3.Connection,
    account_id: int | None = None,
    account_type: str | None = None,
) -> list[dict[str, object]]:
    return TransactionService(connection).opening_balances(account_id, account_type)


def reconcile_account_balance(
    connection: sqlite3.Connection,
    account_id: int,
    reconciliation_date: str,
    known_balance: MoneyInput,
) -> dict[str, object]:
    return TransactionService(connection).reconcile(account_id, reconciliation_date, known_balance)


def import_history(
    connection: sqlite3.Connection,
    account_id: int | None = None,
    account_type: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    return ImportBatchRepository(connection).history(account_id, account_type, limit)
