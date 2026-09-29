"""Create a local development runtime containing only invented financial data."""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

from infrastructure.runtime_config import RuntimeConfig
from institution_support.document_detection import detect_importer
from institution_support.registry import institution_registry
from institutions.eq.document_importers import import_eq_statement_pdf
from repositories.account_ownership_repository import AccountOwnershipRepository
from repositories.account_repository import AccountRepository
from repositories.annual_employment_actual_repository import AnnualEmploymentActualRepository
from repositories.balance_snapshot_repository import BalanceSnapshotRepository
from repositories.employment_baseline_repository import EmploymentBaselineRepository
from repositories.employment_projection_settings_repository import (
    EmploymentProjectionSettingsRepository,
)
from repositories.investment_holding_repository import InvestmentHoldingRepository
from repositories.person_repository import PersonRepository
from repositories.public_rule_approval_repository import PublicRuleApprovalRepository
from repositories.real_estate_asset_repository import RealEstateAssetRepository
from repositories.real_estate_ownership_repository import RealEstateOwnershipRepository
from repositories.scenario_repository import ScenarioRepository
from services.csv_import_service import CsvImportService
from services.database_initialization import ensure_domain_schema
from services.document_import_account_resolver import DocumentImportAccountResolver
from services.public_rule_catalog import PublicRuleCatalog
from services.transaction_service import TransactionService
from synthetic_documents import create_synthetic_fixture_set


def create_synthetic_runtime(data_dir: Path) -> tuple[Path, Path]:
    """Create a new runtime. Refuse to overwrite any existing runtime files."""
    target = data_dir.expanduser().resolve()
    database = target / "finance.sqlite3"
    config = target / "finance.config.json"
    existing = [path for path in (database, config) if path.exists()]
    if existing:
        raise FileExistsError(
            f"Synthetic runtime already exists: {', '.join(path.name for path in existing)}"
        )
    target.mkdir(parents=True, exist_ok=True)
    fixtures = target / "fixtures"
    fixture_set = create_synthetic_fixture_set(fixtures)
    explicit_balance_csv = fixtures / "transactions-with-balances.csv"
    explicit_balance_csv.write_bytes(
        b"Date,Amount,Description,Balance\n"
        b"2026-08-30,100.00,Synthetic transfer,24447.50\n"
        b"2026-08-31,52.50,Synthetic interest,24500.00\n"
    )
    calculated_balance_csv = fixtures / "transactions-without-balances.csv"
    calculated_balance_csv.write_bytes(
        b"Date,Amount,Description\n"
        b"2026-09-01,100.00,Synthetic deposit\n"
        b"2026-09-02,-25.00,Synthetic purchase\n"
        b"2026-09-03,50.00,Synthetic refund\n"
    )
    statement_pdf = fixture_set["sunlife_pdf"]

    with RuntimeConfig(target).connect() as connection:
        ensure_domain_schema(connection)
        accounts = AccountRepository(connection)
        account_owners = AccountOwnershipRepository(connection)
        balances = BalanceSnapshotRepository(connection)
        people = PersonRepository(connection)
        real_estate = RealEstateAssetRepository(connection)
        real_estate_owners = RealEstateOwnershipRepository(connection)
        csv_importer = CsvImportService(connection)
        transactions = TransactionService(connection)
        import_resolver = DocumentImportAccountResolver(connection, institution_registry())

        alex = people.create("Alex Example", "1975-04-12").id
        jordan = people.create("Jordan Example", "1977-09-03").id

        salary_scenario = (
            ScenarioRepository(connection).create("Synthetic salary baseline", "2026-01-01").id
        )
        baselines = EmploymentBaselineRepository(connection)
        salary_settings = EmploymentProjectionSettingsRepository(connection)
        annual_actuals = AnnualEmploymentActualRepository(connection)
        baselines.upsert(alex, "2026-01-01", 105000, "ON", "CPP", "synthetic")
        baselines.upsert(jordan, "2026-01-01", 82000, "QC", "QPP", "synthetic")
        salary_settings.upsert(
            salary_scenario,
            alex,
            default_raise="0.03",
            retirement_date="2031-07-01",
            recurring_rrsp_contribution=12000,
            recurring_rrsp_deduction=12000,
            recurring_other_income=1500,
        )
        salary_settings.upsert(
            salary_scenario,
            jordan,
            default_raise="0.025",
            retirement_date="2033-01-01",
            recurring_rrsp_contribution=9000,
            recurring_rrsp_deduction=9000,
        )
        annual_actuals.upsert(
            alex,
            2025,
            101500,
            other_income=1500,
            rrsp_contribution=11500,
            rrsp_deduction=11500,
            cpp_qpp=4430.1,
            ei=1077.48,
            federal_tax=14500,
            provincial_tax=16800,
            source="synthetic assessment",
        )
        annual_actuals.upsert(
            jordan,
            2025,
            80000,
            rrsp_contribution=8500,
            rrsp_deduction=8500,
            cpp_qpp=4735.2,
            ei=860.67,
            qpip=484.12,
            federal_tax=9100,
            provincial_tax=11200,
            source="synthetic assessment",
        )
        approvals = PublicRuleApprovalRepository(connection)
        catalog = PublicRuleCatalog(Path(__file__).parent / "public_rules")
        for rule_set_id in (
            "ca-2026-official",
            "ca-qc-2026-official",
            "ca-on-2026-official",
        ):
            package = catalog.get(rule_set_id)
            if package is None:  # pragma: no cover - repository package invariant
                raise RuntimeError(f"Missing synthetic public-rule package: {rule_set_id}")
            approvals.approve(rule_set_id, package.content_hash)

        savings = accounts.create(
            "Generic CSV · supplied balances",
            "non_registered",
            account_number="SYN-SAV-001",
            institution="Generic CSV",
        ).id
        account_owners.replace(savings, [(alex, 0.5), (jordan, 0.5)])
        balances.add(savings, "2026-09-01", 24500, 0.0275)
        csv_importer.import_transactions(
            savings,
            explicit_balance_csv.name,
            explicit_balance_csv.read_bytes(),
        )

        calculated = accounts.create(
            "Generic CSV · reconstructed balances",
            "non_registered",
            account_number="SYN-CALC-001",
            institution="Generic CSV",
        ).id
        account_owners.replace(calculated, [(alex, 1.0)])
        balances.add(calculated, "2026-09-03", 5000)
        csv_importer.import_transactions(
            calculated,
            calculated_balance_csv.name,
            calculated_balance_csv.read_bytes(),
        )
        transactions.recalculate_balances(calculated)

        tfsa = accounts.create(
            "Manual balance · TFSA",
            "tfsa",
            account_number="SYN-TFSA-001",
            institution="Manual test",
        ).id
        account_owners.replace(tfsa, [(alex, 1.0)])
        balances.add(tfsa, "2026-09-01", 82000)

        rrsp = accounts.create(
            "Portfolio · holdings and cash",
            "rrsp",
            account_number="SYN-RRSP-001",
            institution="Portfolio test",
        ).id
        account_owners.replace(rrsp, [(jordan, 1.0)])
        balances.add(rrsp, "2026-09-01", 165000)
        holdings = InvestmentHoldingRepository(connection)
        for asset_class, fund_code, fund_name, units, unit_price, market_value in (
            ("Balanced", "SYN-BAL", "Synthetic Balanced Fund", 1200, 100, 120000),
            ("Cash & equivalents", "CASH", "Synthetic Cash", 0, 1, 45000),
        ):
            holdings.upsert(
                rrsp,
                "2026-09-01",
                asset_class,
                fund_code,
                fund_name,
                units,
                unit_price,
                market_value,
                None,
                "synthetic-fixture",
            )

        gic = accounts.create(
            "GIC · linked subaccount",
            "tfsa",
            account_number="SYN-GIC-001",
            institution="Manual test",
            asset_kind="gic",
            parent_account_id=tfsa,
            start_date="2026-01-15",
            maturity_date="2028-01-15",
            principal=20000,
            maturity_value=21800,
            redeemable=False,
        ).id
        account_owners.replace(gic, [(alex, 1.0)])
        balances.add(gic, "2026-09-01", 20600, 0.045)

        consolidated = accounts.create(
            "GIC · parent includes children",
            "tfsa",
            account_number="SYN-TFSA-CONSOLIDATED",
            institution="Consolidation test",
        ).id
        account_owners.replace(consolidated, [(jordan, 1.0)])
        accounts.set_balance_includes_children(consolidated, True)
        balances.add(consolidated, "2026-09-01", 50000)
        included_gic = accounts.create(
            "GIC · included in parent balance",
            "tfsa",
            account_number="SYN-GIC-INCLUDED",
            institution="Consolidation test",
            asset_kind="gic",
            parent_account_id=consolidated,
            start_date="2026-02-01",
            maturity_date="2027-02-01",
            principal=10000,
            maturity_value=10400,
            redeemable=True,
        ).id
        account_owners.replace(included_gic, [(jordan, 1.0)])
        balances.add(included_gic, "2026-09-01", 10250, 0.04)

        home = real_estate.create(
            "Real estate · principal residence",
            525000,
            "2026-09-01",
            property_type="Principal residence",
            acb=400000,
            principal_residence=True,
        ).id
        real_estate_owners.replace(home, [(alex, 0.5), (jordan, 0.5)])

        land = real_estate.create(
            "Land · non-principal property",
            85000,
            "2026-09-01",
            property_type="Vacant land",
            acb=30000,
            principal_residence=False,
        ).id
        real_estate_owners.replace(land, [(alex, 1.0)])

        eq_pdf = fixture_set["eq_pdf"]
        eq_account = accounts.create(
            "PDF TR · EQ",
            "non_registered",
            account_number="999-888-777",
            institution="EQ",
        ).id
        account_owners.replace(eq_account, [(alex, 1.0)])
        import_eq_statement_pdf(connection, eq_account, eq_pdf.name, eq_pdf.read_bytes())

        rbc_deposit = accounts.create(
            "CSV + PDF reconciliation",
            "non_registered",
            account_number="99999-8888888",
            institution="RBC",
        ).id
        account_owners.replace(rbc_deposit, [(alex, 1.0)])
        rbc_csv = fixture_set["rbc_csv"]
        csv_importer.import_transactions(rbc_deposit, rbc_csv.name, rbc_csv.read_bytes())
        rbc_deposit_pdf = fixture_set["rbc_deposit_pdf"]
        rbc_deposit_detected = detect_importer(rbc_deposit_pdf.read_bytes())
        if rbc_deposit_detected is None:
            raise RuntimeError("Synthetic RBC deposit PDF was not recognized")
        rbc_deposit_detected.importer(
            connection,
            rbc_deposit,
            rbc_deposit_pdf.name,
            rbc_deposit_pdf.read_bytes(),
        )

        achieva_parent = accounts.create(
            "PDF GIC TR · Achieva",
            "tfsa",
            account_number="SYN-ACH-001",
            institution="Achieva",
        ).id
        account_owners.replace(achieva_parent, [(alex, 1.0)])
        achieva_pdf = fixture_set["achieva_gic_pdf"]
        achieva_detected = detect_importer(achieva_pdf.read_bytes())
        if achieva_detected is None:
            raise RuntimeError("Synthetic Achieva GIC PDF was not recognized")
        achieva_detected.importer(
            connection,
            achieva_parent,
            achieva_pdf.name,
            achieva_pdf.read_bytes(),
        )

        rbc_tfsa_pdf = fixture_set["rbc_tfsa_pdf"]
        rbc_tfsa_content = rbc_tfsa_pdf.read_bytes()
        rbc_tfsa_detected = detect_importer(rbc_tfsa_content)
        if rbc_tfsa_detected is None:
            raise RuntimeError("Synthetic RBC TFSA PDF was not recognized")
        rbc_tfsa_account = import_resolver.resolve(
            rbc_tfsa_detected.spec.importer_name,
            rbc_tfsa_content,
            rbc_tfsa_pdf.name,
        )
        account_owners.replace(rbc_tfsa_account, [(alex, 1.0)])
        rbc_tfsa_detected.importer(
            connection,
            rbc_tfsa_account,
            rbc_tfsa_pdf.name,
            rbc_tfsa_content,
        )
        accounts.rename(rbc_tfsa_account, "PDF statement + GIC · RBC")

        for fixture_key in ("rbc_maturity_pdf", "rbc_gic_pdf"):
            fixture = fixture_set[fixture_key]
            content = fixture.read_bytes()
            detected_fixture = detect_importer(content)
            if detected_fixture is None:
                raise RuntimeError(f"Synthetic fixture was not recognized: {fixture.name}")
            resolved = import_resolver.resolve(
                detected_fixture.spec.importer_name,
                content,
                fixture.name,
            )
            detected_fixture.importer(connection, resolved, fixture.name, content)

        manulife_pdf = fixture_set["manulife_pdf"]
        manulife_content = manulife_pdf.read_bytes()
        manulife_detected = detect_importer(manulife_content)
        if manulife_detected is None:
            raise RuntimeError("Synthetic Manulife PDF was not recognized")
        manulife_account = import_resolver.resolve(
            manulife_detected.spec.importer_name,
            manulife_content,
            manulife_pdf.name,
        )
        account_owners.replace(manulife_account, [(jordan, 1.0)])
        manulife_detected.importer(
            connection,
            manulife_account,
            manulife_pdf.name,
            manulife_content,
        )
        accounts.rename(manulife_account, "PDF statement + portfolio · Manulife")

        statement_content = statement_pdf.read_bytes()
        detected = detect_importer(statement_content)
        if detected is None:
            raise RuntimeError("Synthetic PDF was not recognized by the parser registry")
        statement_account = import_resolver.resolve(
            detected.spec.importer_name,
            statement_content,
            statement_pdf.name,
        )
        detected.importer(connection, statement_account, statement_pdf.name, statement_content)
        account_owners.replace(statement_account, [(jordan, 1.0)])
        history_pdf = fixture_set["sunlife_history_pdf"]
        history_content = history_pdf.read_bytes()
        history_detected = detect_importer(history_content)
        if history_detected is None:
            raise RuntimeError("Synthetic transaction-history PDF was not recognized")
        history_account = import_resolver.resolve(
            history_detected.spec.importer_name,
            history_content,
            history_pdf.name,
        )
        history_detected.importer(connection, history_account, history_pdf.name, history_content)
        accounts.rename(statement_account, "PDF statement + TR")
        connection.commit()

    config.write_text(
        json.dumps(
            {
                "RUNTIME_ENVIRONMENT": "synthetic",
                "QUESTRADE_CONNECTIONS": [],
                "QUESTRADE_REDIRECT_URI": "https://127.0.0.1:5124/questrade/callback",
                "RETIREMENT_TOKEN_KEY": Fernet.generate_key().decode(),
                "RETIREMENT_APP_SECRET": secrets.token_urlsafe(32),
            },
            indent=2,
        )
        + "\n"
    )
    database.chmod(0o600)
    config.chmod(0o600)
    return database, config


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(description="Create an invented development runtime")
    argument_parser.add_argument("data_dir", type=Path)
    args = argument_parser.parse_args()
    created_database, created_config = create_synthetic_runtime(args.data_dir)
    print(f"Created synthetic database: {created_database}")
    print(f"Created synthetic config: {created_config}")
