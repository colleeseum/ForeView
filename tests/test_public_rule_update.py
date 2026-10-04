from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from reportlab.pdfgen import canvas

from projection.rule_update import (
    FederalRuleProvider,
    HttpSourceRetriever,
    PublicRuleProviderRegistry,
    PublicRuleUpdateService,
    QuebecRuleProvider,
    RetrievedSource,
    cra_jurisdiction_providers,
)
from projection.rule_update.errors import RuleRetrievalError, RuleSourceFormatError
from services.public_rule_catalog import PublicRuleCatalog
from update_public_rules import build_registry, parse_arguments, providers_to_update

FEDERAL_TAX_HTML = b"""
<h2>Federal rate for 2026</h2><table>
<tr><td><p>$0</p></td><td><p>$58,523</p></td><td><p>14%</p></td></tr>
<tr><td><p>$58,523.01</p></td><td><p>$117,045</p></td><td><p>20.5%</p></td></tr>
<tr><td><p>$117,045.01</p></td><td><p>$181,440</p></td><td><p>26%</p></td></tr>
<tr><td><p>$181,440.01</p></td><td><p>$258,482</p></td><td><p>29%</p></td></tr>
<tr><td><p>$258,482.01</p></td><td><p>unlimited</p></td><td><p>33%</p></td></tr>
</table><h2>Provincial or territorial rates</h2>
<h3>Ontario rate: 2026</h3><table>
<tr><td><p>$0</p></td><td><p>$53,891</p></td><td><p>5.05%</p></td></tr>
<tr><td><p>$53,891.01</p></td><td><p>$107,785</p></td><td><p>9.15%</p></td></tr>
<tr><td><p>$107,785.01</p></td><td><p>$150,000</p></td><td><p>11.16%</p></td></tr>
<tr><td><p>$150,000.01</p></td><td><p>$220,000</p></td><td><p>12.16%</p></td></tr>
<tr><td><p>$220,000.01</p></td><td><p>unlimited</p></td><td><p>13.16%</p></td></tr>
</table><h3>Prince Edward Island rate: 2026</h3>
"""

RRSP_LIMIT_HTML = b"""
<table><tr><th>Year</th><th>MP limit</th><th>DB limit</th><th>RRSP dollar limit</th></tr>
<tr><td>2026</td><td>$35,390</td><td>$3,932.22</td><td>$33,810</td></tr></table>
"""
RRSP_FORMULA_HTML = b"<p>The lesser of 18% of previous-year earned income and the annual limit.</p>"
PAYROLL_TABLE_HTML = b"""
<h3>Canada Employment Amount</h3>
<p>The federal CEA is the lesser of: $1,501 and the individual's employment income.</p>
<p>CPP base contribution 74,600.00 3,500.00 71,100.00 0.0495 3,519.45</p>
<p>First additional CPP contribution 74,600.00 3,500.00 71,100.00 0.0100 711.00</p>
<h3>Basic personal amounts</h3><table>
<tr><td>Maximum basic personal amount ($)</td><td>Minimum basic personal amount ($)</td></tr>
<tr><td>16,452</td><td>14,829</td></tr></table>
<table><tr><td>Basic personal amount ($)</td><td>Spouse amount ($)</td></tr>
<tr><td>12,989</td><td>12,000</td></tr></table>
<h3>Surtax</h3><p>Ontario\xe2\x80\x99s surtax is:</p><ul>
<li>basic provincial tax payable is less than or equal to $5,818, the surtax is 0%</li>
<li>greater than $5,818 and less than or equal to $7,446, the surtax is 20%</li>
<li>greater than $7,446, plus 36%</li></ul><h3>Tax reduction</h3>
"""
MANITOBA_PAYROLL_HTML = b"""
<p>The BPAMB for 2026 is $15,780.</p>
"""
MANITOBA_PHASEOUT_HTML = b"""
<p>The Manitoba basic personal amount is reduced for individuals with net income
between $200,000 and $400,000.</p>
"""
QUEBEC_ABATEMENT_HTML = (
    b"<p>The Quebec Abatement consists of a reduction of 16.5 percentage points "
    b"of federal personal income tax.</p>"
)

QUEBEC_TAX_HTML = b"""
<h2>Income tax rates for 2026</h2><table>
<tr><td>$54,345 or less</td><td>14%</td></tr>
<tr><td>More than $54,345 but not more than $108,680</td><td>19%</td></tr>
<tr><td>More than $108,680 but not more than $132,245</td><td>24%</td></tr>
<tr><td>More than $132,245</td><td>25.75%</td></tr>
</table><h2>Income tax rates for 2025</h2>
"""
QPP_HTML = b"""
<table><tr><td>2026</td><td>$3500</td><td>$74 600</td><td>6.3%</td><td>6.3%</td><td>$4479.30</td><td>$8958.60</td></tr></table>
<table><tr><td>2026</td><td>$74 600</td><td>$85 000</td><td>4%</td><td>4%</td><td>$416</td><td>$832</td></tr></table>
"""

CPP_HTML = b"""
<h2>Table 2 - CPP exemptions and pensionable earnings, 2026</h2><table>
<tr><td>Year's Basic Exemption (YBE)</td><td>$3,500.00</td></tr>
<tr><td>Year's Maximum Pensionable Earnings (YMPE)</td><td>$74,600.00</td></tr>
<tr><td>Year's Additional Maximum Pensionable Earnings (YAMPE)</td><td>$85,000.00</td></tr>
</table><h2>Table 3</h2><table>
<tr><td>Contribution rate for employee/employer</td><td>5.95%</td><td>4.00%</td></tr>
<tr><td>Employee/employer maximum contribution</td><td>$4,230.45</td><td>$416.00</td></tr>
</table>
"""
EI_CSV = b"""Table 8.7 Employment Insurance 2026 rates and amounts,,,,,\n
EI,Maximum Annual Insurable Earnings,Employee Contribution Rate,Employer Contribution Rate,Maximum Annual Employee Premium,Maximum Annual Employer Premium\n
Canada except QC,"68,900.00",0.0163,0.02282,"1,123.07","1,572.30"\n
QC,"68,900.00",0.013,0.0182,895.7,"1,253.98"\n
"""
QPIP_CSV = b"""Table 8.8 Quebec Parental Insurance Plan 2026 rates and amounts,,,,,\n
QPIP,Maximum Annual Insurable Earnings,Employee Contribution Rate,Employer Contribution Rate,Maximum Annual Employee Premium,Maximum Annual Employer Premium\n
QC,"103,000.00",0.0043,0.00602,442.90,620.06\n
"""
QPIP_CSV_WITH_SELF_EMPLOYED = b"""QPIP,Maximum Annual Insurable Earnings,Employee Contribution Rate,Employer Contribution Rate,Self-employed Contribution Rate,Maximum Annual Employee Premium,Maximum Annual Employer Premium,Maximum Annual Self-employed Premium\r
QC,"98,000.00",0.00494,0.00692,0.00878,484.12,678.16,860.44\r
"""


def quebec_tax_guide_pdf() -> bytes:
    output = io.BytesIO()
    document = canvas.Canvas(output)
    document.drawString(72, 740, "Personal tax credit amounts 2026")
    document.drawString(72, 720, "Basic personal amount $18,952")
    document.drawString(72, 700, "The maximum deduction for workers is $1,450 for 2026.")
    document.drawString(72, 680, "Deduction for workers = (0.06 x salary), up to the maximum.")
    document.drawString(
        72, 660, "Contribution rate (base contribution rate of 5.30% and additional)"
    )
    document.save()
    return output.getvalue()


class FakeRetriever:
    def __init__(self, content_by_source: dict[str, bytes]) -> None:
        self.content_by_source = content_by_source
        self.calls: list[str] = []

    def retrieve(
        self,
        *,
        source_id: str,
        title: str,
        publisher: str,
        url: str,
        user_agent: str | None = None,
    ) -> RetrievedSource:
        self.calls.append(source_id)
        return RetrievedSource(
            source_id=source_id,
            title=title,
            publisher=publisher,
            url=url,
            content_type="text/html",
            content=self.content_by_source[source_id],
            retrieved_at=datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
        )


def federal_retriever() -> FakeRetriever:
    return FakeRetriever(
        {
            "cra-federal-brackets-2026": FEDERAL_TAX_HTML,
            "cra-registered-plan-limits": RRSP_LIMIT_HTML,
            "cra-rrsp-deduction-limit-formula": RRSP_FORMULA_HTML,
            "cra-payroll-tables-on-2026": PAYROLL_TABLE_HTML,
        }
    )


class PublicRuleProviderTests(unittest.TestCase):
    def test_federal_tax_source_tracks_current_previous_and_historical_years(self):
        self.assertIn(
            "/current-year.html",
            FederalRuleProvider.tax_url(2026, current_year=2026),
        )
        self.assertIn(
            "/last-year.html",
            FederalRuleProvider.tax_url(2025, current_year=2026),
        )
        self.assertIn(
            "/all-years.html",
            FederalRuleProvider.tax_url(2024, current_year=2026),
        )

    def test_federal_provider_extracts_brackets_and_rrsp_rules(self):
        rules = FederalRuleProvider().fetch(2026, federal_retriever())[0]
        self.assertEqual(rules.jurisdiction, "CA")
        self.assertEqual(str(rules.tax_brackets[0].brackets[0].upper_bound), "58523")
        self.assertEqual(str(rules.tax_brackets[0].brackets[-1].rate), "0.33")
        parameters = {item.code: item.value for item in rules.contribution_limits}
        self.assertEqual(parameters["rrsp_annual_dollar_limit"], 33810)
        self.assertEqual(parameters["rrsp_earned_income_rate"], Decimal("0.18"))
        credits = {item.code: item.value for item in rules.credits}
        self.assertEqual(credits["federal_basic_personal_amount_max"], Decimal("16452"))
        self.assertEqual(credits["federal_basic_personal_amount_min"], Decimal("14829"))
        self.assertEqual(credits["canada_employment_amount"], Decimal("1501"))
        payroll = {item.code: item.value for item in rules.payroll_parameters}
        self.assertEqual(payroll["cpp_employee_rate_base"], Decimal("0.0495"))
        self.assertEqual(payroll["cpp_employee_rate_first_additional"], Decimal("0.0100"))

    def test_federal_provider_ignores_explanatory_rates_after_bracket_table(self):
        retriever = federal_retriever()
        retriever.content_by_source["cra-federal-brackets-2026"] = FEDERAL_TAX_HTML.replace(
            b"</table><h2>Provincial",
            b"</table><p>The rate changed from 15% to 14%, making it 14.5%.</p><h2>Provincial",
            1,
        )

        rules = FederalRuleProvider().fetch(2026, retriever)[0]

        self.assertEqual(len(rules.tax_brackets[0].brackets), 5)
        self.assertEqual(rules.tax_brackets[0].brackets[-1].rate, Decimal("0.33"))

    def test_quebec_provider_extracts_tax_and_qpp_rules(self):
        retriever = FakeRetriever(
            {
                "rq-income-tax-rates-2026": QUEBEC_TAX_HTML,
                "rq-qpp-pensionable-earnings-contributions": QPP_HTML,
                "finance-canada-quebec-abatement": QUEBEC_ABATEMENT_HTML,
                "cra-ei-rates-2026": EI_CSV,
                "cra-qpip-rates-2026": QPIP_CSV,
                "rq-tax-formulas-2026": quebec_tax_guide_pdf(),
            }
        )
        rules = QuebecRuleProvider().fetch(2026, retriever)[0]
        self.assertEqual(rules.jurisdiction, "CA-QC")
        self.assertEqual(len(rules.tax_brackets[0].brackets), 4)
        parameters = {item.code: item.value for item in rules.payroll_parameters}
        self.assertEqual(parameters["qpp_ympe"], 74600)
        self.assertEqual(parameters["qpp_yampe"], 85000)
        self.assertEqual(parameters["qpp_employee_rate_first"], Decimal("0.063"))
        self.assertEqual(parameters["qpp_employee_rate_base"], Decimal("0.053"))
        self.assertEqual(parameters["qpp_employee_rate_second"], Decimal("0.04"))
        self.assertEqual(parameters["ei_employee_rate"], Decimal("0.013"))
        self.assertEqual(parameters["ei_employee_max_premium"], Decimal("895.7"))
        self.assertEqual(parameters["qpip_max_insurable_earnings"], Decimal("103000"))
        self.assertEqual(parameters["qpip_employee_rate"], Decimal("0.0043"))
        other = {item.code: item.value for item in rules.other_parameters}
        self.assertEqual(other["quebec_federal_tax_abatement_rate"], Decimal("0.165"))
        self.assertEqual(other["quebec_worker_deduction_max"], Decimal("1450"))
        self.assertEqual(other["quebec_worker_deduction_rate"], Decimal("0.06"))
        credits = {item.code: item.value for item in rules.credits}
        self.assertEqual(credits["quebec_basic_personal_amount"], Decimal("18952"))

    def test_payroll_csv_sources_accept_carriage_return_line_endings(self):
        retriever = FakeRetriever(
            {
                "rq-income-tax-rates-2026": QUEBEC_TAX_HTML,
                "rq-qpp-pensionable-earnings-contributions": QPP_HTML,
                "finance-canada-quebec-abatement": QUEBEC_ABATEMENT_HTML,
                "cra-ei-rates-2026": EI_CSV.replace(b"\n", b"\r"),
                "cra-qpip-rates-2026": QPIP_CSV.replace(b"\n", b"\r"),
                "rq-tax-formulas-2026": quebec_tax_guide_pdf(),
            }
        )

        rules = QuebecRuleProvider().fetch(2026, retriever)[0]

        parameters = {item.code: item.value for item in rules.payroll_parameters}
        self.assertEqual(parameters["ei_employee_rate"], Decimal("0.013"))
        self.assertEqual(parameters["qpip_employee_rate"], Decimal("0.0043"))

    def test_qpip_parser_uses_headers_when_a_year_has_extra_columns(self):
        retriever = FakeRetriever(
            {
                "rq-income-tax-rates-2026": QUEBEC_TAX_HTML,
                "rq-qpp-pensionable-earnings-contributions": QPP_HTML,
                "finance-canada-quebec-abatement": QUEBEC_ABATEMENT_HTML,
                "cra-ei-rates-2026": EI_CSV,
                "cra-qpip-rates-2026": QPIP_CSV_WITH_SELF_EMPLOYED,
                "rq-tax-formulas-2026": quebec_tax_guide_pdf(),
            }
        )

        rules = QuebecRuleProvider().fetch(2026, retriever)[0]

        parameters = {item.code: item.value for item in rules.payroll_parameters}
        self.assertEqual(parameters["qpip_employee_rate"], Decimal("0.00494"))
        self.assertEqual(parameters["qpip_employee_max_premium"], Decimal("484.12"))

    def test_ontario_provider_extracts_tax_and_cpp_rules(self):
        retriever = FakeRetriever(
            {
                "cra-on-brackets-2026": FEDERAL_TAX_HTML,
                "esdc-cpp-figures-2026": CPP_HTML,
                "cra-payroll-tables-on-2026": PAYROLL_TABLE_HTML,
                "cra-ei-rates-2026": EI_CSV,
            }
        )
        provider = next(
            provider for provider in cra_jurisdiction_providers() if provider.provider_id == "ca.on"
        )
        rules = provider.fetch(2026, retriever)[0]
        self.assertEqual(rules.jurisdiction, "CA-ON")
        self.assertEqual(len(rules.tax_brackets[0].brackets), 5)
        parameters = {item.code: item.value for item in rules.payroll_parameters}
        self.assertEqual(parameters["cpp_basic_exemption"], 3500)
        self.assertEqual(parameters["cpp_employee_max_first"], Decimal("4230.45"))
        self.assertEqual(parameters["cpp_employee_rate_first"], Decimal("0.0595"))
        self.assertEqual(parameters["ei_max_insurable_earnings"], Decimal("68900"))
        self.assertEqual(parameters["ei_employee_rate"], Decimal("0.0163"))
        self.assertEqual(parameters["ei_employee_max_premium"], Decimal("1123.07"))
        other = {item.code: item.value for item in rules.other_parameters}
        self.assertEqual(other["ontario_basic_personal_amount"], Decimal("12989"))
        self.assertEqual(other["ontario_surtax_threshold_first"], Decimal("5818"))
        self.assertEqual(other["ontario_surtax_rate_second"], Decimal("0.36"))

    def test_manitoba_provider_extracts_bpa_phaseout_rules(self):
        retriever = FakeRetriever(
            {
                "cra-mb-brackets-2026": FEDERAL_TAX_HTML.replace(
                    b"<h3>Ontario rate: 2026</h3>", b"<h3>Manitoba rate: 2026</h3>"
                ).replace(
                    b"<h3>Prince Edward Island rate: 2026</h3>",
                    b"<h3>New Brunswick rate: 2026</h3>",
                ),
                "esdc-cpp-figures-2026": CPP_HTML,
                "cra-payroll-tables-mb-2026": MANITOBA_PAYROLL_HTML,
                "cra-manitoba-bpa-phaseout": MANITOBA_PHASEOUT_HTML,
            }
        )
        provider = next(
            provider for provider in cra_jurisdiction_providers() if provider.provider_id == "ca.mb"
        )

        rules = provider.fetch(2026, retriever)[0]

        parameters = {item.code: item.value for item in rules.other_parameters}
        self.assertEqual(parameters["manitoba_basic_personal_amount"], Decimal("15780"))
        self.assertEqual(parameters["manitoba_bpa_phaseout_start"], Decimal("200000"))
        self.assertEqual(parameters["manitoba_bpa_phaseout_end"], Decimal("400000"))

    def test_source_format_change_fails_instead_of_creating_partial_rules(self):
        retriever = federal_retriever()
        retriever.content_by_source["cra-federal-brackets-2026"] = b"<p>changed</p>"
        with self.assertRaises(RuleSourceFormatError):
            FederalRuleProvider().fetch(2026, retriever)


class PublicRuleUpdateServiceTests(unittest.TestCase):
    def test_committed_2025_packages_have_expected_official_values(self):
        catalog = PublicRuleCatalog(Path(__file__).parents[1] / "public_rules")
        packages = catalog.list_packages()
        for tax_year in (2025, 2026):
            self.assertEqual(
                len([package for package in packages if package.rule_set.tax_year == tax_year]),
                14,
            )
        federal = catalog.get("ca-2025-official")
        quebec = catalog.get("ca-qc-2025-official")
        ontario = catalog.get("ca-on-2025-official")
        self.assertIsNotNone(federal)
        self.assertIsNotNone(quebec)
        self.assertIsNotNone(ontario)

        self.assertEqual(federal.rule_set.tax_brackets[0].brackets[0].rate, Decimal("0.145"))
        self.assertEqual(federal.rule_set.contribution_limits[0].value, Decimal("32490"))
        self.assertEqual(quebec.rule_set.tax_brackets[0].brackets[0].upper_bound, 53255)
        self.assertEqual(ontario.rule_set.tax_brackets[0].brackets[0].upper_bound, 52886)
        cpp = {item.code: item.value for item in ontario.rule_set.payroll_parameters}
        self.assertEqual(cpp["cpp_ympe"], Decimal("71300"))

    def test_command_defaults_to_current_tax_year(self):
        self.assertEqual(parse_arguments([]).year, date.today().year)

    def test_registry_rejects_duplicates_and_unknown_providers(self):
        registry = PublicRuleProviderRegistry()
        registry.register(FederalRuleProvider())
        self.assertEqual(registry.list_all()[0].provider_id, "ca.federal")
        with self.assertRaises(ValueError):
            registry.register(FederalRuleProvider())
        with self.assertRaisesRegex(KeyError, "Unknown public-rule provider"):
            registry.get("missing")

    def test_default_registry_contains_federal_quebec_and_every_other_jurisdiction(self):
        providers = build_registry().list_all()
        self.assertEqual(len(providers), 14)
        self.assertEqual(
            {provider.jurisdiction for provider in providers},
            {
                "CA",
                "CA-AB",
                "CA-BC",
                "CA-MB",
                "CA-NB",
                "CA-NL",
                "CA-NS",
                "CA-NT",
                "CA-NU",
                "CA-ON",
                "CA-PE",
                "CA-QC",
                "CA-SK",
                "CA-YT",
            },
        )

    def test_completed_packages_are_skipped_unless_force_is_requested(self):
        registry = PublicRuleProviderRegistry()
        registry.register(FederalRuleProvider())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            PublicRuleUpdateService(registry, federal_retriever()).update(
                2026, ["ca.federal"], root
            )

            pending, skipped = providers_to_update(
                registry, root, 2026, ["ca.federal"], force=False
            )
            forced, force_skipped = providers_to_update(
                registry, root, 2026, ["ca.federal"], force=True
            )

        self.assertEqual(pending, [])
        self.assertEqual(skipped, ["ca.federal"])
        self.assertEqual(forced, ["ca.federal"])
        self.assertEqual(force_skipped, [])

    def test_tampered_package_is_not_considered_downloaded(self):
        registry = PublicRuleProviderRegistry()
        registry.register(FederalRuleProvider())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = PublicRuleUpdateService(registry, federal_retriever()).update(
                2026, ["ca.federal"], root
            )[0]
            rule_path = result.package_directory / "ca-2026-official.json"
            rule_path.write_text("tampered")

            pending, skipped = providers_to_update(
                registry, root, 2026, ["ca.federal"], force=False
            )

        self.assertEqual(pending, ["ca.federal"])
        self.assertEqual(skipped, [])

    def test_update_writes_versioned_sources_and_hashes_without_runtime_approval(self):
        registry = PublicRuleProviderRegistry()
        registry.register(FederalRuleProvider())
        with tempfile.TemporaryDirectory() as directory:
            results = PublicRuleUpdateService(registry, federal_retriever()).update(
                2026, ["ca.federal"], Path(directory)
            )
            result = results[0]
            manifest_path = result.package_directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertNotIn("candidate_status", manifest)
            self.assertEqual(len(manifest["sources"]), 4)
            self.assertEqual(len(manifest["rule_sets"]), 1)
            self.assertTrue((result.package_directory / "ca-2026-official.json").exists())
            for source in manifest["sources"]:
                self.assertTrue((result.package_directory / source["filename"]).exists())

    def test_update_rejects_invalid_year(self):
        with self.assertRaises(ValueError):
            PublicRuleUpdateService(PublicRuleProviderRegistry(), federal_retriever()).update(
                1999, [], Path("unused")
            )

    def test_catalog_verifies_generated_packages_and_rejects_source_tampering(self):
        registry = PublicRuleProviderRegistry()
        registry.register(FederalRuleProvider())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = PublicRuleUpdateService(registry, federal_retriever()).update(
                2026, ["ca.federal"], root
            )[0]
            package = PublicRuleCatalog(root).get("ca-2026-official")
            self.assertIsNotNone(package)
            self.assertEqual(package.content_hash, result.rule_set_hashes[0])

            source_path = result.package_directory / "sources/cra-federal-brackets-2026.html"
            source_path.write_bytes(source_path.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                PublicRuleCatalog(root).list_packages()

    def test_catalog_rejects_rule_hash_missing_file_and_unsafe_source_path(self):
        for defect in ("rule_hash", "missing_rule", "unsafe_source"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                registry = PublicRuleProviderRegistry()
                registry.register(FederalRuleProvider())
                result = PublicRuleUpdateService(registry, federal_retriever()).update(
                    2026, ["ca.federal"], root
                )[0]
                manifest_path = result.package_directory / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                if defect == "rule_hash":
                    manifest["rule_sets"][0]["sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest))
                    expected = "does not match its manifest"
                elif defect == "missing_rule":
                    (result.package_directory / manifest["rule_sets"][0]["filename"]).unlink()
                    expected = "file is missing"
                else:
                    manifest["sources"][0]["filename"] = "../outside.html"
                    manifest_path.write_text(json.dumps(manifest))
                    expected = "Unsafe public-rule filename"
                with self.assertRaisesRegex(ValueError, expected):
                    PublicRuleCatalog(root).list_packages()

        self.assertIsNone(PublicRuleCatalog(Path("missing")).get("unknown"))


class HttpSourceRetrieverTests(unittest.TestCase):
    class Headers:
        @staticmethod
        def get_content_type() -> str:
            return "text/html"

    class Response:
        def __init__(self, content: bytes, url: str = "https://official.example/rules") -> None:
            self._content = content
            self._url = url
            self.headers = HttpSourceRetrieverTests.Headers()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def geturl(self) -> str:
            return self._url

        def read(self, limit: int) -> bytes:
            return self._content

    def test_retriever_accepts_bounded_https_content(self):
        with patch(
            "projection.rule_update.http_retriever.urllib.request.urlopen",
            return_value=self.Response(b"official"),
        ) as urlopen:
            source = HttpSourceRetriever().retrieve(
                source_id="official",
                title="Official",
                publisher="Authority",
                url="https://official.example/rules",
            )
        self.assertEqual(source.content, b"official")
        self.assertEqual(len(source.content_hash), 64)
        request = urlopen.call_args.args[0]
        self.assertIsNone(request.get_header("User-agent"))

    def test_retriever_applies_an_explicit_source_user_agent(self):
        with patch(
            "projection.rule_update.http_retriever.urllib.request.urlopen",
            return_value=self.Response(b"official"),
        ) as urlopen:
            HttpSourceRetriever().retrieve(
                source_id="official",
                title="Official",
                publisher="Authority",
                url="https://official.example/rules",
                user_agent="Source-Compatible/1.0",
            )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "Source-Compatible/1.0")

    def test_retriever_reuses_one_download_for_shared_official_urls(self):
        retriever = HttpSourceRetriever()
        with patch(
            "projection.rule_update.http_retriever.urllib.request.urlopen",
            return_value=self.Response(b"official"),
        ) as urlopen:
            first = retriever.retrieve(
                source_id="first",
                title="First",
                publisher="Authority",
                url="https://official.example/rules",
            )
            second = retriever.retrieve(
                source_id="second",
                title="Second",
                publisher="Authority",
                url="https://official.example/rules",
            )

        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(second.source_id, "second")
        self.assertEqual(second.content, first.content)
        self.assertEqual(second.retrieved_at, first.retrieved_at)

    def test_retriever_rejects_http_oversized_empty_and_network_failures(self):
        retriever = HttpSourceRetriever(maximum_bytes=4)
        with self.assertRaises(RuleRetrievalError):
            retriever.retrieve(
                source_id="http",
                title="HTTP",
                publisher="Authority",
                url="http://official.example/rules",
            )
        for content in (b"12345", b""):
            with (
                self.subTest(content=content),
                patch(
                    "projection.rule_update.http_retriever.urllib.request.urlopen",
                    return_value=self.Response(content),
                ),
            ):
                with self.assertRaises(RuleRetrievalError):
                    retriever.retrieve(
                        source_id="official",
                        title="Official",
                        publisher="Authority",
                        url="https://official.example/rules",
                    )
        with patch(
            "projection.rule_update.http_retriever.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaises(RuleRetrievalError):
                retriever.retrieve(
                    source_id="official",
                    title="Official",
                    publisher="Authority",
                    url="https://official.example/rules",
                )


if __name__ == "__main__":
    unittest.main()
