# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Canonical service imports must work in a fresh process, without eager barrels."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("app_first", [False, True])
def test_grouped_service_identity_and_fresh_startup(tmp_path: Path, app_first: bool) -> None:
    root = Path(__file__).parents[1]
    assert sorted(path.name for path in (root / "services").glob("*.py")) == ["__init__.py"]
    code = """
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

packages = ("services.accounts", "services.reporting", "services.projections", "services.income", "services.imports", "services.expenses", "services.runtime", "services.transactions")
for name in packages:
    importlib.import_module(name)
assert not any(name.startswith(tuple(package + "." for package in packages)) for name in sys.modules)
if sys.argv[2] == "True":
    import app
from services.accounts.account_aggregation_service import AccountAggregationService
from services.accounts.account_summary_query import AccountSummaryQuery
from services.accounts.fixed_term_deposit_creation_service import FixedTermDepositCreationService
from services.accounts.real_estate_summary_query import RealEstateSummaryQuery
from services.reporting.dashboard import build_dashboard_summary
from services.reporting.dashboard_query import DashboardQuery
from services.reporting.reporting_query import ReportingQuery
from services.projections.public_rule_catalog import PublicRuleCatalog
from services.projections.salary_projection_service import SalaryProjectionService
from services.projections.scenario_clone_service import ScenarioCloneService
from services.income.factual_correction_validator import FactualCorrectionValidator
from services.income.income_tax_snapshot_service import IncomeTaxSnapshotService
from services.income.income_tax_source_resolver import IncomeTaxSourceResolver, source_fingerprint
from services.imports.csv_import_service import CsvImportService
from services.imports.document_import_account_resolver import DocumentImportAccountResolver
from services.imports.ufile_tax_return_parser import UFileTaxReturnParser
from services.imports.cra_notice_parser import CraNoticeParser
from services.imports.revenu_quebec_notice_parser import RevenuQuebecNoticeParser
from services.imports.retraite_quebec_statement_parser import RetraiteQuebecStatementParser
from services.expenses.expense_import_service import ExpenseImportService
from services.expenses.expense_service import ExpenseService
from services.transactions.transaction_service import TransactionService
from services.transactions.reconciliation_checkpoint_service import ReconciliationCheckpointService
from services.runtime.database_initialization import initialize_database, ensure_domain_schema
from services.runtime.imported_transaction_repair import ImportedTransactionRepair
from services.runtime.legacy_fixed_deposit_migration import LegacyFixedDepositMigration
from services.runtime.runtime_backup_service import RuntimeBackupService
import app
from infrastructure.runtime_config import RuntimeConfig
from web import account_routes, dashboard_routes, public_rule_routes, real_estate_routes, reporting_routes, salary_projection_routes
from web import income_routes, correction_routes, correction_serialization, transaction_routes, expense_routes
from services.reporting import dashboard_query
from services.runtime import database_initialization
from ingestion import reconciled_period_guard
from institutions.questrade import sync as questrade_sync
from institutions.sunlife import import_service as sunlife_import
from institutions.manulife import import_service as manulife_import
from institutions.rbc import deposit_import_service, gic_history_import_service, tfsa_import_service
import runtime_backup
import synthetic_expenses
import synthetic_questrade
from income_sources import income_source_registry
from tax_notices import tax_notice_registry
from public_pension_sources import public_pension_source_registry
import synthetic_runtime
from tests import support

bindings = (
    (account_routes.AccountAggregationService, AccountAggregationService),
    (account_routes.AccountSummaryQuery, AccountSummaryQuery),
    (account_routes.FixedTermDepositCreationService, FixedTermDepositCreationService),
    (real_estate_routes.RealEstateSummaryQuery, RealEstateSummaryQuery),
    (dashboard_routes.DashboardQuery, DashboardQuery),
    (reporting_routes.ReportingQuery, ReportingQuery),
    (public_rule_routes.PublicRuleCatalog, PublicRuleCatalog),
    (salary_projection_routes.SalaryProjectionService, SalaryProjectionService),
    (salary_projection_routes.ScenarioCloneService, ScenarioCloneService),
    (dashboard_query.build_dashboard_summary, build_dashboard_summary),
    (synthetic_runtime.PublicRuleCatalog, PublicRuleCatalog),
    (support.AccountSummaryQuery, AccountSummaryQuery),
    (income_routes.IncomeTaxSnapshotService, IncomeTaxSnapshotService),
    (income_routes.IncomeTaxSourceResolver, IncomeTaxSourceResolver),
    (correction_routes.FactualCorrectionValidator, FactualCorrectionValidator),
    (correction_routes.source_fingerprint, source_fingerprint),
    (correction_serialization.source_fingerprint, source_fingerprint),
    (transaction_routes.CsvImportService, CsvImportService),
    (transaction_routes.DocumentImportAccountResolver, DocumentImportAccountResolver),
    (database_initialization.CsvImportService, CsvImportService),
    (synthetic_runtime.CsvImportService, CsvImportService),
    (support.CsvImportService, CsvImportService),
    (expense_routes.ExpenseImportService, ExpenseImportService),
    (expense_routes.ExpenseService, ExpenseService),
    (app.ensure_domain_schema, ensure_domain_schema),
    (app.initialize_database, initialize_database),
    (synthetic_runtime.ensure_domain_schema, ensure_domain_schema),
    (synthetic_expenses.initialize_database, initialize_database),
    (synthetic_questrade.initialize_database, initialize_database),
    (runtime_backup.RuntimeBackupService, RuntimeBackupService),
    (database_initialization.ImportedTransactionRepair, ImportedTransactionRepair),
    (database_initialization.LegacyFixedDepositMigration, LegacyFixedDepositMigration),
    (transaction_routes.TransactionService, TransactionService),
    (account_routes.TransactionService, TransactionService),
    (dashboard_query.TransactionService, TransactionService),
    (questrade_sync.TransactionService, TransactionService),
    (sunlife_import.TransactionService, TransactionService),
    (manulife_import.TransactionService, TransactionService),
    (deposit_import_service.TransactionService, TransactionService),
    (gic_history_import_service.TransactionService, TransactionService),
    (tfsa_import_service.TransactionService, TransactionService),
    (reconciled_period_guard.ReconciliationCheckpointService, ReconciliationCheckpointService),
    (transaction_routes.ReconciliationCheckpointService, ReconciliationCheckpointService),
    (deposit_import_service.ReconciliationCheckpointService, ReconciliationCheckpointService),
)
assert all(actual is canonical for actual, canonical in bindings)
for symbol in (AccountAggregationService, AccountSummaryQuery, FixedTermDepositCreationService, RealEstateSummaryQuery, build_dashboard_summary, DashboardQuery, ReportingQuery, PublicRuleCatalog, SalaryProjectionService, ScenarioCloneService, FactualCorrectionValidator, IncomeTaxSnapshotService, IncomeTaxSourceResolver, CsvImportService, DocumentImportAccountResolver, UFileTaxReturnParser, CraNoticeParser, RevenuQuebecNoticeParser, RetraiteQuebecStatementParser, ExpenseImportService, ExpenseService, TransactionService, ReconciliationCheckpointService, initialize_database, ImportedTransactionRepair, LegacyFixedDepositMigration, RuntimeBackupService):
    old = "services." + symbol.__module__.rsplit(".", 1)[1]
    assert importlib.util.find_spec(old) is None
    assert old not in sys.modules
provider_bindings = (
    (income_source_registry.providers[0], UFileTaxReturnParser),
    (tax_notice_registry.providers[0], CraNoticeParser),
    (tax_notice_registry.providers[1], RevenuQuebecNoticeParser),
    (public_pension_source_registry.providers[0], RetraiteQuebecStatementParser),
)
for provider, parser in provider_bindings:
    assert type(provider.parser.__self__) is parser
    assert provider.parser.__func__ is parser.parse
    assert provider.detects is parser.detects
    sentinel = RuntimeError("canonical parser patch")
    with patch.object(importlib.import_module(parser.__module__).pdfplumber, "open", side_effect=sentinel) as reader:
        try:
            provider.parser(b"synthetic")
        except RuntimeError as error:
            assert error is sentinel
        else:
            raise AssertionError("Provider did not use canonical parser dependency")
        reader.assert_called_once()
runtime = RuntimeConfig(Path(sys.argv[1]))
app.initialize(runtime)
application = app.create_app(runtime)
client = application.test_client()
with patch.object(dashboard_routes, "DashboardQuery") as query:
    query.return_value.execute.return_value = {"sentinel": "use-site"}
    assert client.get("/api/dashboard").get_json() == {"sentinel": "use-site"}
    query.return_value.execute.assert_called_once()
for url in ("/api/dashboard", "/api/model/accounts", "/api/model/real-estate", "/api/model/annual-summary", "/api/model/holdings", "/api/model/import-history", "/api/salary-projection", "/api/institutions", "/api/income?person_id=1", "/api/income/sources", "/api/expenses"):
    response = client.get(url)
    assert response.status_code == 200, (url, response.status_code)
assert client.get("/settings").status_code == 200
print("SERVICE_LAYOUT_PASSED")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "runtime"), str(app_first)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SERVICE_LAYOUT_PASSED" in result.stdout
