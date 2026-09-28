import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from institution_support.document_detection import detect_importer
from institutions.manulife.parser import parse_rrsp_statement
from tests.support import (
    account_summary,
    add_balance_snapshot,
    add_fixed_term_deposit,
    create_account,
    create_person,
    create_scenario,
    ensure_domain_schema,
    import_achieva_gic_pdf,
    import_csv_transactions,
    import_pdf_transactions,
    import_rbc_statement_pdf,
    import_rbc_tfsa_pdf,
    parse_eq_pdf_transactions,
    parse_rbc_gic_transaction_history,
    parse_rbc_tfsa_statement,
    recalculate_transaction_balances,
    set_account_current_interest_rate,
    set_account_owners,
    set_scenario_assumption,
    transaction_summary,
    update_account,
    update_person_birth_date,
)

ROOT = Path(__file__).parents[1]
_SQLITE_CONNECT = sqlite3.connect


class ModelImportTests(unittest.TestCase):
    def setUp(self):
        self.connections = []
        patcher = patch.object(sqlite3, "connect", side_effect=self._tracked_connect)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _tracked_connect(self, *args, **kwargs):
        connection = _SQLITE_CONNECT(*args, **kwargs)
        self.connections.append(connection)
        self.addCleanup(connection.close)
        return connection

    def test_manulife_rrsp_parser_reconciles_period_totals(self):
        pages = [
            """Annual report:
Manulife Financial Personal Plan
Your customer number: 999000112
January 1, 2025 to December 31, 2025
Personal Registered Savings Plan (RRSP)
What happened in your plan this period
Opening value $1,769,441.76 $1,769,441.76
Plus contributions for:
Jan1,2025toMar3,2025 $0.00 $0.00
Mar4,2025toDec31,2025 $0.00 $0.00
Plus savings bonus $9,310.08 $9,310.08
Plus growth in value $203,513.37 $203,513.37
Value on December 31, 2025 $1,982,265.21 $1,982,265.21
Your plan assets are not locked in.
"""
        ]
        parsed = parse_rrsp_statement(pages)
        self.assertEqual(parsed["account_number"], "999000112")
        self.assertEqual(parsed["closing_value"], 1982265.21)
        self.assertEqual(round(sum(row["amount"] for row in parsed["rows"]), 2), 212823.45)

    def test_parser_registry_detects_rbc_gic_history(self):
        from unittest.mock import patch

        with patch(
            "institutions.rbc.document_importers.is_rbc_gic_transaction_history_pdf",
            return_value=True,
        ):
            detected = detect_importer(b"%PDF-test", "RBC")
        self.assertIsNotNone(detected)
        self.assertEqual(detected.spec.document_type, "gic")

    def test_joint_account_ownership_is_explicit(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        primary = create_person(connection, "Alex Example", "1970-01-01")
        secondary = create_person(connection, "Jordan Example", "1972-01-01")
        account = create_account(
            connection, "Joint savings", "non_registered", account_number="joint-1"
        )
        set_account_owners(connection, account, [(primary, 0.5), (secondary, 0.5)])
        owners = connection.execute(
            "SELECT COUNT(*), SUM(ownership_share) FROM account_owners WHERE account_id = ?",
            (account,),
        ).fetchone()
        self.assertEqual(owners[0], 2)
        self.assertAlmostEqual(owners[1], 1.0)
        self.assertEqual(
            connection.execute("SELECT birth_date FROM people WHERE id = ?", (primary,)).fetchone()[
                0
            ],
            "1970-01-01",
        )
        update_person_birth_date(connection, primary, "1970-02-02")
        self.assertEqual(
            connection.execute("SELECT birth_date FROM people WHERE id = ?", (primary,)).fetchone()[
                0
            ],
            "1970-02-02",
        )

        with self.assertRaises(ValueError):
            set_account_owners(connection, account, [(primary, 0.6), (secondary, 0.6)])

    def test_gic_and_scenario_are_separate_from_account_balance(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(connection, "RBC GIC", "non_registered", account_number="gic-1")
        deposit = add_fixed_term_deposit(
            connection,
            account,
            "Five year GIC",
            10000,
            0.0565,
            "2026-01-01",
            "2031-01-01",
            redeemable=False,
        )
        scenario = create_scenario(connection, "Baseline 2026", "2026-01-01")
        set_scenario_assumption(connection, scenario, "general_growth_rate", "0.04", "annual_rate")
        self.assertGreater(deposit, 0)
        self.assertEqual(
            connection.execute(
                "SELECT interest_rate FROM fixed_term_deposits WHERE id = ?", (deposit,)
            ).fetchone()[0],
            0.0565,
        )
        self.assertEqual(
            connection.execute(
                "SELECT value FROM scenario_assumptions WHERE scenario_id = ? AND key = ?",
                (scenario, "general_growth_rate"),
            ).fetchone()[0],
            "0.04",
        )

    def test_gic_uses_the_same_account_model_with_parent_link(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        parent = create_account(
            connection, "Achieva TFSA", "tfsa", account_number="9901", institution="Achieva"
        )
        gic = create_account(
            connection,
            "24 Month TFSA GIC-2",
            "tfsa",
            account_number="",
            institution="Achieva",
            asset_kind="gic",
            parent_account_id=parent,
            start_date="2025-08-05",
            maturity_date="2027-08-05",
            maturity_value=171512.13,
            principal=150000,
        )
        row = connection.execute(
            "SELECT asset_kind, parent_account_id, maturity_date, principal FROM accounts WHERE id = ?",
            (gic,),
        ).fetchone()
        self.assertEqual(tuple(row), ("gic", parent, "2027-08-05", 150000.0))
        self.assertTrue(
            connection.execute("SELECT account_number FROM accounts WHERE id = ?", (gic,))
            .fetchone()[0]
            .startswith("gic:")
        )
        self.assertEqual(
            connection.execute(
                "SELECT parent_name FROM (SELECT a.id, parent.name AS parent_name FROM accounts a LEFT JOIN accounts parent ON parent.id = a.parent_account_id) WHERE id = ?",
                (gic,),
            ).fetchone()[0],
            "Achieva TFSA",
        )

    def test_gic_can_move_to_another_parent_account(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        first = create_account(connection, "First TFSA", "tfsa", account_number="tfsa-1")
        second = create_account(connection, "Second TFSA", "tfsa", account_number="tfsa-2")
        gic = create_account(
            connection,
            "GIC-1",
            "tfsa",
            account_number="",
            asset_kind="gic",
            parent_account_id=first,
            maturity_date="2027-01-01",
        )
        update_account(
            connection,
            gic,
            name="GIC-1",
            account_number="gic:1:GIC-1:2027-01-01",
            institution=None,
            category="tfsa",
            asset_kind="gic",
            parent_account_id=second,
            maturity_date="2027-01-01",
        )
        row = connection.execute(
            "SELECT parent_account_id, account_number FROM accounts WHERE id = ?", (gic,)
        ).fetchone()
        self.assertEqual(tuple(row), (second, f"gic:{second}:GIC-1:2027-01-01"))

    def test_account_number_is_required_and_name_is_editable(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        with self.assertRaises(ValueError):
            create_account(connection, "TFSA", "tfsa", account_number="")
        account = create_account(connection, None, "tfsa", account_number="12345")
        update_account(
            connection,
            account,
            name="Alex TFSA",
            account_number="54321",
            institution="Questrade",
            category="tfsa",
        )
        row = connection.execute(
            "SELECT name, account_number FROM accounts WHERE id = ?", (account,)
        ).fetchone()
        self.assertEqual(tuple(row), ("Alex TFSA", "54321"))

    def test_balance_can_store_current_annual_rate(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(connection, "Savings", "non_registered", account_number="s-1")
        add_balance_snapshot(connection, account, "2026-01-01", 50000, 0.0275)
        row = connection.execute(
            "SELECT amount, interest_rate FROM balance_snapshots WHERE account_id = ?",
            (account,),
        ).fetchone()
        self.assertEqual(tuple(row), (50000.0, 0.0275))

    def test_account_can_store_current_rate_without_balance_snapshot(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(
            connection, "Jordan account", "non_registered", account_number="g-1"
        )
        set_account_current_interest_rate(connection, account, 0.0275)
        self.assertEqual(
            connection.execute(
                "SELECT current_interest_rate FROM accounts WHERE id = ?", (account,)
            ).fetchone()[0],
            0.0275,
        )

    def test_account_summary_uses_latest_imported_transaction_balance(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        account = create_account(
            connection, "Imported account", "non_registered", account_number="imported-1"
        )
        import_csv_transactions(
            connection,
            account,
            "balance.csv",
            b"Date,Amount,Description,Balance\n2026-03-01,25,Deposit,125\n",
        )
        summary = account_summary(connection)[0]
        self.assertEqual(summary["latest_date"], "2026-03-01")
        self.assertEqual(summary["latest_amount"], 125.0)

    def test_account_summary_does_not_duplicate_owner_for_multiple_latest_snapshots(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        secondary = create_person(connection, "Jordan Example")
        account = create_account(connection, "Savings", "tfsa", account_number="s-1")
        set_account_owners(connection, account, [(secondary, 1.0)])
        connection.executemany(
            "INSERT INTO balance_snapshots(account_id, snapshot_date, amount, source_sheet, source_address) VALUES (?, ?, ?, ?, ?)",
            [
                (account, "2026-08-05", 100.0, "import-a", "A1"),
                (account, "2026-08-05", 100.0, "import-b", "A1"),
            ],
        )
        connection.commit()
        self.assertEqual(account_summary(connection)[0]["owners"], "Jordan Example (100.0%)")

    def test_csv_transaction_import_preserves_rows_and_rejects_duplicate_file(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(connection, "Checking", "non_registered", account_number="c-1")
        csv_content = b"Date,Amount,Description,Balance\n2026-01-01,-25.50,Groceries,1000.00\n2026-01-02,100.00,Pay,1100.00\n"
        first = import_csv_transactions(connection, account, "bank.csv", csv_content)
        second = import_csv_transactions(connection, account, "bank.csv", csv_content)
        self.assertEqual(first["imported"], 2)
        self.assertEqual(second["status"], "already_imported")
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM raw_transactions").fetchone()[0], 2
        )
        self.assertEqual(
            connection.execute("SELECT SUM(amount) FROM transactions").fetchone()[0], 74.5
        )

    def test_csv_import_normalizes_day_month_name_dates(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(
            connection, "Achieva", "non_registered", account_number="achieva-1"
        )
        result = import_csv_transactions(
            connection,
            account,
            "achieva.csv",
            b"Date,Description,Amount,Balance\n31Oct2025,Credit Interest,$25.56,$471535.36\n",
        )
        self.assertEqual(result["imported"], 1)
        row = connection.execute("SELECT transaction_date FROM transactions").fetchone()
        self.assertEqual(row[0], "2025-10-31")

    def test_rbc_canada_csv_profile_maps_french_headers_and_validates_account(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(
            connection,
            "RBC chequing",
            "non_registered",
            account_number="99999-7777777",
            institution="RBC",
        )
        content = "﻿Type de compte,Numéro du compte,Date de l'opération,Numéro du chèque,Description 1,Description 2,CAD$,USD$\nChèques,99999-7777777,1/2/2025,,DÉPÔT DE CHÈQUE,,21.98,\nChèques,99999-7777777,1/6/2025,,VIREMENT ENVOYÉ,, -100,\n".encode()
        result = import_csv_transactions(connection, account, "rbc.csv", content)
        self.assertEqual(result["imported"], 2)
        rows = connection.execute(
            "SELECT transaction_date, amount, description FROM transactions ORDER BY id"
        ).fetchall()
        self.assertEqual(tuple(rows[0]), ("2025-01-02", 21.98, "DÉPÔT DE CHÈQUE"))
        self.assertEqual(rows[1][1], -100.0)

    def test_missing_csv_balances_are_reconstructed_from_known_balance(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(
            connection, "RBC chequing", "non_registered", account_number="rbc-1", institution="RBC"
        )
        import_csv_transactions(
            connection,
            account,
            "rbc.csv",
            b"Date,Amount,Description\n2026-01-01,10,Deposit\n2026-01-02,-4,Fee\n",
        )
        add_balance_snapshot(connection, account, "2026-01-02", 106)
        updated = recalculate_transaction_balances(connection, account)
        self.assertEqual(updated, 2)
        balances = [
            row[0]
            for row in connection.execute(
                "SELECT balance_after FROM transactions ORDER BY transaction_date"
            )
        ]
        self.assertEqual(balances, [110.0, 106.0])

    def test_rbc_pdf_reconciles_csv_activity_to_statement_closing_balance(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(
            connection,
            "RBC chequing",
            "non_registered",
            account_number="99999-7777777",
            institution="RBC",
        )
        import_csv_transactions(
            connection,
            account,
            "rbc.csv",
            b"Date,Amount,Description\n2026-08-19,-105.51,Energy\n2026-08-31,48000,Deposit\n2026-08-31,-49230,Payment\n",
        )
        from unittest.mock import patch

        summary = {
            "account_number": "99999-7777777",
            "statement_start": "2026-08-14",
            "statement_end": "2026-09-14",
            "opening_balance": 9541.20,
            "closing_balance": 8205.69,
            "statement_deposits": 48000.0,
            "statement_withdrawals": 49335.51,
        }
        with patch(
            "institutions.rbc.document_importers.parse_rbc_statement_summary", return_value=summary
        ):
            result = import_rbc_statement_pdf(connection, account, "statement.pdf", b"pdf")
        self.assertEqual(result["reconciliation_status"], "reconciled")
        self.assertEqual(result["difference"], 0.0)
        self.assertEqual(
            connection.execute(
                "SELECT amount FROM balance_snapshots WHERE account_id = ?", (account,)
            ).fetchone()[0],
            8205.69,
        )
        balances = [
            row[0]
            for row in connection.execute(
                "SELECT balance_after FROM transactions ORDER BY transaction_date"
            )
        ]
        self.assertEqual(balances, [9435.69, 57435.69, 8205.69])

    def test_rbc_tfsa_statement_parses_savings_activity_and_gic(self):
        pages = [
            """Votre relevé de placements
1 janvier 2025 au 31 décembre 2025
Votre n° de compte Votre succursale
999888770 000RUEEXEMPLE
Compte d'épargne libre d'impôt
Total $81,347.25 $84,993.18 $3,645.93
Activité de vos placements avec Banque Royale du Canada
Activité de vos dépôts d'épargne
Solded'ouverture 4,307.61
30jun2025 Intérêtsréinvesti 10.20 4,317.81
26sep2025 IntérêtsCPGversésàl'épargne 4,288.35 8,606.16
31déc2025 Intérêtsréinvesti 13.02 8,619.18
31déc2025 Soldedeclôture 8,619.18
Activité de vos CPG
BanqueRoyaleCPG
000000001 26sep2025 75,900.00 2.350 76,374.00 26sep2026 77,694.12
"""
        ]
        result = parse_rbc_tfsa_statement(pages)
        self.assertEqual(result["account_number"], "999888770")
        self.assertEqual(result["closing_value"], 84993.18)
        self.assertEqual(len(result["savings_events"]), 3)
        self.assertEqual(result["gics"][0]["maturity_date"], "2026-09-26")
        self.assertEqual(result["gics"][0]["interest_rate"], 0.0235)

    def test_rbc_tfsa_pdf_imports_statement_and_upserts_gic(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        account = create_account(
            connection, "RBC TFSA", "tfsa", account_number="999888770", institution="RBC"
        )
        pages = [
            """Votre relevé de placements
1 janvier 2025 au 31 décembre 2025
Votre n° de compte Votre succursale
999888770 000RUEEXEMPLE
Compte d'épargne libre d'impôt
Total $81,347.25 $84,993.18 $3,645.93
Activité de vos dépôts d'épargne
30jun2025 Intérêtsréinvesti 10.20 4,317.81
31déc2025 Intérêtsréinvesti 13.02 8,619.18
Activité de vos CPG
BanqueRoyaleCPG
000000001 26sep2025 75,900.00 2.350 76,374.00 26sep2026 77,694.12
"""
        ]
        from unittest.mock import patch

        class FakePage:
            def __init__(self, text):
                self.text = text

            def extract_text(self):
                return self.text

        page_text = pages[0]

        class FakePdf:
            pages = [FakePage(page_text)]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch("tests.support.pdfplumber.open", return_value=FakePdf()):
            result = import_rbc_tfsa_pdf(connection, account, "tfsa.pdf", b"pdf bytes")
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["gics"], 1)
        self.assertEqual(
            connection.execute(
                "SELECT amount FROM balance_snapshots WHERE account_id = ?", (account,)
            ).fetchone()[0],
            84993.18,
        )
        self.assertEqual(account_summary(connection)[0]["latest_amount"], 84993.18)
        row = connection.execute("SELECT description, category FROM transactions").fetchone()
        self.assertEqual(tuple(row), ("Interest reinvested", "Interest"))
        self.assertEqual(
            transaction_summary(connection, account_type="tfsa")[0]["combined_balance_after"],
            84993.18,
        )
        gic = connection.execute(
            "SELECT principal, interest_rate, maturity_value FROM fixed_term_deposits"
        ).fetchone()
        self.assertEqual(tuple(gic), (75900.0, 0.0235, 77694.12))

    def test_rbc_tfsa_maturity_notice_updates_existing_gic(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(
            connection, "RBC TFSA", "tfsa", account_number="999888770", institution="RBC"
        )
        pages = [
            """Avis d’échéance de CPG
Compte d'épargne libre d'impôt
Numéro de compte : 999888770
Date de l’avis : 18 septembre, 2026
Numéro de certificate : 000000001 • Émetteur : Banque Royale du Canada Date d’échéance : 26 septembre,
26 septembre, 2025 75 900,00 $ 2,350 % 77 694,12 $
"""
        ]
        from unittest.mock import patch

        class FakePage:
            def extract_text(self):
                return pages[0]

        class FakePdf:
            pages = [FakePage()]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch("tests.support.pdfplumber.open", return_value=FakePdf()):
            result = import_rbc_tfsa_pdf(connection, account, "notice.pdf", b"notice bytes")
        self.assertEqual(result["document_type"], "maturity_notice")
        self.assertEqual(
            connection.execute("SELECT maturity_date FROM fixed_term_deposits").fetchone()[0],
            "2026-09-26",
        )

    def test_rbc_english_maturity_notice_parses_gic_details(self):
        pages = [
            """Royal Bank of Canada
GIC Maturity Notice
Tax-Free Savings Account
Account Number: 999888771
Date: September 22, 2026
TFSA Term Deposit
Certificate #: 000000001 • Issued by: Royal Bank of Canada Maturity Date: September 28, 2026
Investment Date Amount Invested Interest Rate Maturity Value
September 26, 2023 $7,500.00 5.350% $7,500.00
Your maturity instruction
"""
        ]
        result = parse_rbc_tfsa_statement(pages, "notice.pdf")
        self.assertEqual(result["account_number"], "999888771")
        self.assertEqual(result["gics"][0]["maturity_date"], "2026-09-28")
        self.assertAlmostEqual(result["gics"][0]["interest_rate"], 0.0535)

    def test_achieva_gic_pdf_imports_linked_subaccount_and_interest_history(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        secondary = create_person(connection, "Jordan Example")
        parent = create_account(
            connection, "Achieva TFSA", "tfsa", account_number="9901", institution="Achieva"
        )
        set_account_owners(connection, parent, [(secondary, 1.0)])
        pdf_text = """Transactions
24 Month TFSA GIC-2
$171,512.13
Wed, Aug 05, 2026
System Generated Entry credit
$5,799.93 $171,512.13
interest 5,799.93
Sat, Aug 05, 2023
Tax Sheltered TFSA Transfer Credit
$150,000.00 $150,000.00
tfsa 0
"""
        from unittest.mock import patch

        class FakePage:
            def extract_text(self):
                return pdf_text

        class FakePdf:
            pages = [FakePage()]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch("tests.support.pdfplumber.open", return_value=FakePdf()):
            result = import_achieva_gic_pdf(connection, parent, "GIC.pdf", b"achieva gic pdf")
        self.assertEqual(result["imported"], 2)
        child = connection.execute(
            "SELECT id, asset_kind, parent_account_id FROM accounts WHERE asset_kind = 'gic'"
        ).fetchone()
        self.assertEqual(tuple(child), (child[0], "gic", parent))
        self.assertEqual(
            connection.execute(
                "SELECT amount FROM balance_snapshots WHERE account_id = ?", (child[0],)
            ).fetchone()[0],
            171512.13,
        )

    def test_multiple_monthly_csv_files_can_be_imported(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(connection, "EQ savings", "non_registered", account_number="eq-1")
        january = b"Date,Amount,Description\n2026-01-01,10,Deposit\n"
        february = b"Date,Amount,Description\n2026-02-01,-5,Fee\n"
        first = import_csv_transactions(connection, account, "2026-01.csv", january)
        second = import_csv_transactions(connection, account, "2026-02.csv", february)
        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["imported"], 1)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 2)

    def test_all_transactions_include_combined_balance(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        first = create_account(connection, "First", "non_registered", account_number="first")
        second = create_account(connection, "Second", "non_registered", account_number="second")
        import_csv_transactions(
            connection,
            first,
            "first.csv",
            b"Date,Amount,Description,Balance\n2026-01-01,10,Deposit,110\n",
        )
        import_csv_transactions(
            connection,
            second,
            "second.csv",
            b"Date,Amount,Description,Balance\n2026-01-02,20,Deposit,220\n",
        )
        all_rows = transaction_summary(connection)
        self.assertEqual(all_rows[0]["combined_balance_after"], 330.0)
        self.assertEqual(transaction_summary(connection, first)[0]["balance_after"], 110.0)

    def test_linked_gic_is_added_to_parent_cash_balance(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        parent = create_account(connection, "Achieva TFSA", "tfsa", account_number="tfsa-1")
        gic = create_account(
            connection,
            "GIC-2",
            "tfsa",
            account_number="",
            institution="Achieva",
            asset_kind="gic",
            parent_account_id=parent,
            start_date="2025-08-05",
            maturity_date="2027-08-05",
            maturity_value=171512.13,
            principal=150000,
        )
        import_csv_transactions(
            connection,
            parent,
            "parent.csv",
            b"Date,Amount,Description,Balance\n2026-08-05,5799.93,Cash interest,72435.99\n",
        )
        import_csv_transactions(
            connection,
            gic,
            "gic.csv",
            b"Date,Amount,Description,Balance\n2026-08-05,5799.93,GIC interest,171512.13\n",
        )
        rows = transaction_summary(connection, account_type="tfsa")
        self.assertEqual([row["combined_balance_after"] for row in rows], [243948.12, 238148.19])

    def test_parent_account_transaction_filter_includes_gic_children(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        parent = create_account(connection, "RBC TFSA", "tfsa", account_number="tfsa-parent")
        child = create_account(
            connection,
            "RBC GIC 000000001",
            "tfsa",
            account_number="gic-cert",
            asset_kind="gic",
            parent_account_id=parent,
        )
        import_csv_transactions(
            connection,
            child,
            "gic.csv",
            b"Date,Amount,Description,Balance\n2026-09-01,10,Interest,110\n",
        )
        rows = transaction_summary(connection, account_id=parent)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["account_id"], child)

    def test_combined_total_prefers_newer_balance_snapshot(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        account = create_account(
            connection, "Savings", "non_registered", account_number="snapshot-1"
        )
        import_csv_transactions(
            connection,
            account,
            "history.csv",
            b"Date,Amount,Description,Balance\n2026-09-01,10,Deposit,100\n",
        )
        add_balance_snapshot(connection, account, "2026-09-23", 120)
        rows = transaction_summary(connection, account_type="non_registered")
        self.assertEqual(rows[0]["combined_balance_after"], 120.0)

    def test_eq_pdf_parser_reads_deposits_withdrawals_and_balance(self):
        pages = [
            """January 2026 Statement
Saving Account # 123-456-789 January 1, 2026 to January 31, 2026
Activity details
Date Description Withdrawals Deposits Balance
Jan 12 Interac e-Transfer received $100.00 $100.00
Jan 15 Auto-withdrawal - $7.00 $93.00
Jan 31 Interest received $0.20 $93.20
"""
        ]
        account_number, rows = parse_eq_pdf_transactions(pages)
        self.assertEqual(account_number, "123456789")
        self.assertEqual([row["amount"] for row in rows], [100.0, -7.0, 0.2])
        self.assertEqual(rows[0]["description"], "Interac e-Transfer received")
        self.assertEqual(rows[-1]["balance"], 93.2)

    def test_rbc_gic_transaction_history_parser_reads_gic_rows(self):
        pages = [
            """Account Transaction History As of 24 Sep 2026
TFSA.. 999888771
TFSA Term Deposit #000000001
Total
Date Description Value
Value
24 Jul 2025 Opening Balance 7,472.52
26 Sep 2025 GIC Interest Paid to Savings 401.25 7,873.77
24 Sep 2026 Accrued Interest 26.37 7,900.14
24 Sep 2026 Closing Balance 7,900.14
RBC Savings Deposit
Total
Date Description Value
Value
24 Sep 2026 Closing Balance 809.73
"""
        ]
        parsed = parse_rbc_gic_transaction_history(pages)
        self.assertEqual(parsed["account_number"], "999888771")
        self.assertEqual(parsed["closing_value"], 7900.14)
        self.assertEqual(parsed["savings_closing"], 809.73)
        self.assertEqual([row["amount"] for row in parsed["rows"]], [401.25, 26.37])

    def test_eq_pdf_import_validates_account_and_preserves_rows(self):
        connection = sqlite3.connect(":memory:")
        ensure_domain_schema(connection)
        account = create_account(
            connection, "EQ savings", "non_registered", account_number="123-456-789"
        )
        pdf_text = """January 2026 Statement
Saving Account # 123-456-789 January 1, 2026 to January 31, 2026
Jan 12 Deposit $100.00 $100.00
Jan 15 Withdrawal - $7.00 $93.00
"""
        from unittest.mock import patch

        class FakePage:
            def extract_text(self):
                return pdf_text

        class FakePdf:
            pages = [FakePage()]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with patch("tests.support.pdfplumber.open", return_value=FakePdf()):
            result = import_pdf_transactions(connection, account, "statement.pdf", b"pdf bytes")
        self.assertEqual(result["imported"], 2)
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM raw_transactions").fetchone()[0], 2
        )
        self.assertEqual(
            connection.execute("SELECT SUM(amount) FROM transactions").fetchone()[0], 93.0
        )


if __name__ == "__main__":
    unittest.main()
