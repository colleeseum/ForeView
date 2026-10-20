# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Canonical service imports must work in a fresh process, without eager barrels."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("app_first", [False, True])
def test_grouped_service_identity_and_fresh_startup(tmp_path: Path, app_first: bool) -> None:
    code = """
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

for name in ("services.accounts", "services.reporting", "services.projections"):
    importlib.import_module(name)
assert not any(name.startswith(("services.accounts.", "services.reporting.", "services.projections.")) for name in sys.modules)
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
import app
from infrastructure.runtime_config import RuntimeConfig
from web import account_routes, dashboard_routes, public_rule_routes, real_estate_routes, reporting_routes, salary_projection_routes
from services.reporting import dashboard_query
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
)
assert all(actual is canonical for actual, canonical in bindings)
for symbol in (AccountAggregationService, AccountSummaryQuery, FixedTermDepositCreationService, RealEstateSummaryQuery, build_dashboard_summary, DashboardQuery, ReportingQuery, PublicRuleCatalog, SalaryProjectionService, ScenarioCloneService):
    old = "services." + symbol.__module__.rsplit(".", 1)[1]
    assert importlib.util.find_spec(old) is None
    assert old not in sys.modules
runtime = RuntimeConfig(Path(sys.argv[1]))
app.initialize(runtime)
application = app.create_app(runtime)
client = application.test_client()
with patch.object(dashboard_routes, "DashboardQuery") as query:
    query.return_value.execute.return_value = {"sentinel": "use-site"}
    assert client.get("/api/dashboard").get_json() == {"sentinel": "use-site"}
    query.return_value.execute.assert_called_once()
for url in ("/api/dashboard", "/api/model/accounts", "/api/model/real-estate", "/api/model/annual-summary", "/api/model/holdings", "/api/model/import-history", "/api/salary-projection", "/api/institutions"):
    response = client.get(url)
    assert response.status_code == 200, (url, response.status_code)
assert client.get("/settings").status_code == 200
print("SERVICE_LAYOUT_PASSED")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "runtime"), str(app_first)],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SERVICE_LAYOUT_PASSED" in result.stdout
