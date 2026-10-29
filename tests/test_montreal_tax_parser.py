# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from decimal import Decimal

import pytest

from devtools.synthetic.synthetic_documents import create_synthetic_montreal_tax_statement
from domain.validation_error import ValidationError
from expense_sources.montreal_tax import provider
from expense_sources.montreal_tax.parser import MontrealTaxParser, TaxAccountText
from expense_sources.registry import expense_source_registry

FRONT = """Municipal Tax Account 2026
Account number Reference number Access code Taxation period Billing date
000001-00 00000001-26-01-00 Day Month Year Day Month Year Day Month Year
01 01 2026 to 31 12 2026 28 01 2026
Debtor(s) of the account Property location
Alex Example 123 Example Street
Borough: Synthetic Borough
Taxable value(s) on December 31, 2025: 600 000
Breakdown of account (See the appendix) Tax base Rate Amount
VILLE DE MONTRÉAL
GENERAL TAX 600 000 0,5000 /$100 3 000,01
TAX CONTRIBUTION 600 000 0,0167 /$100 100,01
BOROUGH
TAX CONCERNING SERVICES 600 000 0,1500 /$100 900,01
Due date(s) Day Month Year Amount Day Month Year Amount Account total
1st: 02 03 2026 2 000,01 2nd: 01 06 2026 2 000,02 4 000,03
Interest and penalty may apply to overdue payments.
2nd Instalment - Please attach to your 2nd payment
Instalment payable Amount paid
2 000,02
1st Instalment - Please attach to your 1st payment
Instalment payable Amount paid
2 000,01
"""
BACK = "Terms of payment\nOption - 6 instalments with interests and penalty\n$700,00"
FR_FRONT = """Compte de taxes municipales 2026
Numéro de compte Numéro de référence Code d'accès Période d'imposition Date de facturation
000001-00 00000001-26-01-00 Jour Mois Année Jour Mois Année Jour Mois Année
01 01 2026 au 31 12 2026 28 01 2026
Débiteur(s) du compte Emplacement de la propriété
Alex Example 123 Example Street
Arrondissement : Quartier fictif
Détail du compte (Consulter l'annexe jointe au compte) Base d'imposition Taux Montant
VILLE DE MONTRÉAL
TAXE GÉNÉRALE 600 000 0,5000 /100$ 3 000,01
TAXE CONTRIBUTION 600 000 0,0167 /100$ 100,01
ARRONDISSEMENT
TAXE RELATIVE AUX SERVICES 600 000 0,1500 /100$ 900,01
Total du compte
Date(s) limite(s) Jour Mois Année Montant Jour Mois Année Montant
versement(s) 1e r : 02 03 2026 2 000,01 2 e : 01 06 2026 2 000,02 4 000,03
Versement 2 - À joindre à votre 2e paiement
Montant à payer Montant versé
2 000,02
Versement 1 - À joindre à votre 1er paiement
2 000,01
"""
FR_BACK = "Modalités de paiement\nOption - 6 versements avec intérêts et pénalité\n700,00 $"


def parser(front=FRONT, back=BACK, location="123 Example Street"):
    return MontrealTaxParser(lambda _: TaxAccountText((front, back), location))


def test_annual_obligation_not_installments_payment_plan_or_taxable_value():
    result = parser().parse(b"synthetic")
    assert result.amount == Decimal("4000.03")
    assert result.period_start == date(2026, 1, 1)
    assert result.period_end == date(2026, 12, 31)
    assert result.period_kind == "annual_or_one_time"
    assert (
        result.suggested_identity
        == "Montréal municipal property tax · 123 Example Street · 000001-00"
    )
    assert "Alex" not in result.suggested_identity
    assert parser().detects(b"synthetic")


@pytest.mark.parametrize("language", ["en", "fr"])
def test_real_synthetic_pdf_discovery_and_property_column(tmp_path, language):
    content = create_synthetic_montreal_tax_statement(
        tmp_path / "tax.pdf", language=language
    ).read_bytes()
    detected = expense_source_registry.detect(content)
    assert detected.key == "montreal-tax"
    assert detected.parser(content) == parser().parse(b"synthetic")
    assert detected.version == MontrealTaxParser.VERSION
    assert provider().translations["fr-CA"]["help_text"]


def test_french_source_has_same_identity_dates_and_annual_amount_as_english():
    source = parser(FR_FRONT, FR_BACK)
    assert source.detects(b"synthetic")
    assert source.parse(b"synthetic") == parser().parse(b"synthetic")


@pytest.mark.parametrize(
    "old,new,code",
    [
        ("4 000,03", "4 000,04", "amount"),
        ("3 000,01", "-3 000,01", "amount"),
        ("3 000,01", "3 000,01 CR", "amount"),
        ("3 000,01", "3 000,001", "amount"),
        ("3 000,01", "3 00,01", "amount"),
        ("3 000,01", "NaN", "amount"),
        ("3 000,01", "9999999999999999999999,00", "amount"),
        ("2 000,01", "2 000,02", "amount"),
        ("/100$", "/$100", "amount"),
        ("Total du compte\n", "", "amount"),
        ("Total du compte\n", "Total du compte\nTotal du compte\n", "amount"),
        ("versement(s) 1e r", "versement(s) 2e", "amount"),
        ("01 01 2026 au", "02 01 2026 au", "period"),
        ("31 12 2026", "31 12 2025", "period"),
        ("31 12 2026", "31 02 2026", "period"),
        ("28 01 2026", "30 02 2026", "period"),
        ("02 03 2026", "01 06 2026", "period"),
        ("000001-00", "missing", "identity"),
        ("VILLE DE MONTRÉAL", "AUTRE VILLE", "format"),
        ("Compte de taxes municipales", "Compte rectifié de taxes municipales", "format"),
    ],
)
def test_french_validation_rejects_ambiguous_or_inconsistent_evidence(old, new, code):
    with pytest.raises(ValidationError) as error:
        parser(FR_FRONT.replace(old, new), FR_BACK).parse(b"synthetic")
    assert error.value.code == f"expense_montreal_{code}"


@pytest.mark.parametrize("front,back", [(FR_FRONT, BACK), (FRONT, FR_BACK), (FR_FRONT, FR_FRONT)])
def test_mixed_source_layouts_or_multiple_annual_bills_are_rejected(front, back):
    with pytest.raises(ValidationError) as error:
        parser(front, back).parse(b"synthetic")
    assert error.value.code == "expense_montreal_format"


@pytest.mark.parametrize("year", [2024, 2025, 2028])
def test_calendar_year_including_leap_years(year):
    result = parser(FRONT.replace("2026", str(year))).parse(b"synthetic")
    assert result.period_start == date(year, 1, 1)
    assert result.period_end == date(year, 12, 31)


@pytest.mark.parametrize(
    "old,new",
    [
        ("01 01 2026 to", "02 01 2026 to"),
        ("31 12 2026", "30 12 2026"),
        ("31 12 2026", "31 12 2025"),
        ("31 12 2026", "31 02 2026"),
        ("Municipal Tax Account 2026", "Municipal Tax Account 2025"),
        ("28 01 2026", "30 02 2026"),
        ("02 03 2026", "02 03 2027"),
        ("02 03 2026", "01 06 2026"),
        ("01 06 2026", "01 01 2026"),
        ("02 03 2026", "31 02 2026"),
    ],
)
def test_invalid_partial_mismatched_or_unordered_periods(old, new):
    with pytest.raises(ValidationError) as error:
        parser(FRONT.replace(old, new)).parse(b"synthetic")
    assert error.value.code == "expense_montreal_period"


@pytest.mark.parametrize(
    "old,new",
    [
        ("4 000,03", "4 000,04"),
        ("3 000,01", "3 000,02"),
        ("2 000,01", "2 000,02"),
        ("4 000,03", "NaN"),
        ("4 000,03", "4 000,031"),
        ("4 000,03", "40 00,03"),
        ("4 000,03", "-4 000,03"),
        ("3 000,01", "−3 000,01"),
        ("3 000,01", "(3 000,01)"),
        ("3 000,01", "3 000,01 CR"),
        ("3 000,01", "999999999999999999999999,00"),
        ("/$100 3 000,01", "fixed charge 3 000,01"),
        ("Account total", "Outstanding balance"),
        ("GENERAL TAX 600 000 0,5000 /$100 3 000,01\n", ""),
    ],
)
def test_missing_malformed_negative_or_inconsistent_money_is_rejected(old, new):
    with pytest.raises(ValidationError) as error:
        parser(FRONT.replace(old, new)).parse(b"synthetic")
    assert error.value.code == "expense_montreal_amount"


def test_zero_is_valid_only_when_explicit_and_all_evidence_agrees():
    front = FRONT
    for value in ("3 000,01", "100,01", "900,01", "2 000,01", "2 000,02", "4 000,03"):
        front = front.replace(value, "0,00")
    assert parser(front).parse(b"synthetic").amount == Decimal("0.00")


def test_unicode_grouping_and_coupon_values_do_not_change_the_obligation():
    front = FRONT.replace("3 000,01", "3\u202f000,01").replace("4 000,03", "4\u00a0000,03")
    front += "\nInstalment payable 999 999,99\nAmount paid 123,45\n"
    assert parser(front).parse(b"synthetic").amount == Decimal("4000.03")


@pytest.mark.parametrize(
    "front,back",
    [
        (FRONT.replace("VILLE DE MONTRÉAL", "OTHER CITY"), BACK),
        (FRONT.replace("Municipal Tax Account", "Transfer duties"), BACK),
        (FRONT.replace("Municipal Tax Account", "Corrected Municipal Tax Account"), BACK),
        (FRONT + FRONT, BACK),
        (FRONT, FRONT),
        (FRONT, ""),
    ],
)
def test_foreign_nonannual_corrected_bundled_and_incomplete_layouts_fail(front, back):
    with pytest.raises(ValidationError) as error:
        parser(front, back).parse(b"synthetic")
    assert error.value.code == "expense_montreal_format"


@pytest.mark.parametrize(
    "front,location",
    [
        (FRONT.replace("000001-00", "missing"), "123 Example Street"),
        (FRONT, ""),
    ],
)
def test_missing_property_identity_is_not_fabricated(front, location):
    with pytest.raises(ValidationError) as error:
        parser(front, location=location).parse(b"synthetic")
    assert error.value.code == "expense_montreal_identity"


def test_unreadable_blank_or_extra_page_documents_fail():
    for content in (b"", b"not a PDF"):
        assert not MontrealTaxParser().detects(content)
        with pytest.raises(ValidationError) as error:
            MontrealTaxParser().parse(content)
        assert error.value.code == "expense_montreal_unreadable"
    for document in (TaxAccountText(()), TaxAccountText(("", " "))):
        assert not MontrealTaxParser(lambda _, document=document: document).detects(b"synthetic")
    with pytest.raises(ValidationError):
        MontrealTaxParser(lambda _: TaxAccountText((FRONT, BACK, BACK))).parse(b"synthetic")
