# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from decimal import Decimal

import pytest

from devtools.synthetic.synthetic_documents import create_synthetic_energir_statement
from domain.validation_error import ValidationError
from expense_sources.energir import EnergirParser, provider
from expense_sources.registry import expense_source_registry

FRONT = """Énergir, s.e.c. / Énergir, L.P.
Pour la période du 2025 DE 15 au / to 2026 JA 14
Solde précédent 300,00 $
Paiement reçu 300,00 $CR
Montant facturé pour la période du /
Amount Billed for the Period from
2025 DE 15 au / to 2026 JA 14
2025 NO 15 2025 DE 14 30 80R 90,00
Volume facturé / Volume billed: 100 m3 (voir verso 100,00 $
TPS / GST (no / # 000000001) 5,00 $
Total de l'année courante TVQ / PST (no / # 000000002) 9,98 $
2024 DE 15 2025 DE 14 365 1500 1 999,99 Total 114,98 $ 114,98 $
Montant courant / Current amount 114,98 $
Prélèvement automatique 114,98 $CR
Montant total à payer / Total Amount to Pay 0,00 $
"""
BACK = """Énergir
Période / Period : 2025 DE 15 au / to 2026 JA 14 31 jours / days
Calcul du volume facturé / Calculation of the Billed Volume
Total avant taxes / Total before taxes 100,00 $
"""


def parser(front=FRONT, back=BACK):
    return EnergirParser(lambda content: [front, back])


def test_current_gas_charge_not_due_balance_history_or_automatic_payment():
    source = parser()
    assert source.detects(b"synthetic")
    result = source.parse(b"synthetic")
    assert result.amount == Decimal("114.98")
    assert result.period_start == date(2025, 12, 15)
    assert result.period_end == date(2026, 1, 14)
    assert result.suggested_identity == "Énergir"
    assert result.period_kind == "recurring_statement"


def test_real_synthetic_pdf_is_discovered_and_parsed(tmp_path):
    content = create_synthetic_energir_statement(tmp_path / "synthetic-energir.pdf").read_bytes()
    detected = expense_source_registry.detect(content)
    assert detected.key == "energir"
    assert detected.parser(content).amount == Decimal("114.98")
    assert provider().version == EnergirParser.VERSION
    assert provider().translations["fr-CA"]["display_name"]


@pytest.mark.parametrize("month", "JA FE MR AL MA JN JL AU SE OC NO DE".split())
def test_month_codes_and_one_day_inclusive_period(month):
    front = FRONT.replace("2025 DE 15", f"2024 {month} 05").replace(
        "2026 JA 14", f"2024 {month} 05"
    )
    back = (
        BACK.replace("2025 DE 15", f"2024 {month} 05")
        .replace("2026 JA 14", f"2024 {month} 05")
        .replace("31 jours", "1 jours")
    )
    result = parser(front, back).parse(b"synthetic")
    assert result.period_start == result.period_end
    assert (
        result.period_start.month == "JA FE MR AL MA JN JL AU SE OC NO DE".split().index(month) + 1
    )


@pytest.mark.parametrize(
    "start,end,days",
    [
        ("2024 FE 28", "2024 MR 01", "3"),
        ("2025 FE 28", "2025 MR 01", "2"),
    ],
)
def test_leap_day_period(start, end, days):
    front = FRONT.replace("2025 DE 15", start).replace("2026 JA 14", end)
    back = (
        BACK.replace("2025 DE 15", start)
        .replace("2026 JA 14", end)
        .replace("31 jours", f"{days} jours")
    )
    result = parser(front, back).parse(b"synthetic")
    assert (result.period_end - result.period_start).days + 1 == int(days)


@pytest.mark.parametrize(
    "front,back",
    [
        (FRONT, BACK.replace("31 jours", "30 jours")),
        (FRONT, BACK.replace("2026 JA 14", "2026 JA 15")),
        (FRONT.replace("2025 DE 15", "2025 FE 30"), BACK),
        (FRONT.replace("2026 JA 14", "2024 JA 14"), BACK),
        (FRONT + "Pour la période du 2025 DE 15 au / to 2026 JA 14", BACK),
        (FRONT, ""),
    ],
)
def test_invalid_or_ambiguous_periods_fail(front, back):
    with pytest.raises(ValidationError) as error:
        parser(front, back).parse(b"synthetic")
    assert error.value.code == "expense_energir_period"


@pytest.mark.parametrize(
    "old,new",
    [
        ("100,00 $", "100,001 $"),
        ("100,00 $", "123 45,67 $"),
        ("100,00 $", "NaN $"),
        ("100,00 $", "99999999999999999999999999999999999,00 $"),
        ("100,00 $", "1e2 $"),
        ("5,00 $", "5,00 $CR"),
        ("5,00 $", "5,00 $ (CR)"),
        ("5,00 $", "-5,00 $"),
        ("5,00 $", "- 5,00 $"),
        ("5,00 $", "(- 5,00 $)"),
        ("5,00 $", "5,00 $\nCR"),
        ("5,00 $", "−5,00 $"),
        ("5,00 $", "‐5,00 $"),
        ("5,00 $", "(5,00 $)"),
        ("9,98 $", "10,00 $"),
        ("Total 114,98 $ 114,98 $", "Total 114,98 $ 0,00 $"),
        ("Total 114,98 $ 114,98 $", "Montant dû 114,98 $"),
        ("TPS / GST", "Unknown tax"),
        ("TVQ / PST", "Unknown tax"),
        ("Total 114,98 $ 114,98 $", "Total 114,98 $\nTotal 114,98 $"),
    ],
)
def test_amount_validation_rejects_missing_credit_negative_ambiguous_or_inconsistent_data(old, new):
    with pytest.raises(ValidationError) as error:
        parser(FRONT.replace(old, new)).parse(b"synthetic")
    assert error.value.code == "expense_energir_amount"


def test_explicit_zero_and_grouped_amounts():
    zero = (
        FRONT.replace("100,00 $", "0,00 $")
        .replace("5,00 $", "0,00 $")
        .replace("9,98 $", "0,00 $")
        .replace("114,98 $", "0,00 $")
    )
    assert parser(zero).parse(b"synthetic").amount == Decimal("0.00")
    grouped = (
        FRONT.replace("100,00 $", "1\u202f000,00 $")
        .replace("5,00 $", "50,00 $")
        .replace("9,98 $", "99,75 $")
        .replace("114,98 $", "1\u00a0149,75 $")
    )
    assert parser(grouped).parse(b"synthetic").amount == Decimal("1149.75")


@pytest.mark.parametrize(
    "marker",
    [
        "Mode de paiements égaux",
        "MPÉ",
        "EPP",
        "Facture corrigée",
        "Annual review",
    ],
)
def test_unsupported_bundles_and_payment_plans_are_rejected(marker):
    with pytest.raises(ValidationError) as error:
        parser(FRONT + marker).parse(b"synthetic")
    assert error.value.code == "expense_energir_unsupported"


@pytest.mark.parametrize("marker", ["Location (chauffe-eau) 10,00 $", "Rental equipment 10,00 $"])
def test_rental_charges_are_rejected_in_billed_charge_section(marker):
    front = FRONT.replace("Montant courant", marker + "\nMontant courant")
    with pytest.raises(ValidationError) as error:
        parser(front).parse(b"synthetic")
    assert error.value.code == "expense_energir_unsupported"


@pytest.mark.parametrize(
    "front,back",
    [
        ("ABC Location\n" + FRONT, BACK),
        ("Rental Services Example\n" + FRONT, BACK),
        (FRONT + "Learn about rental services", BACK),
        (FRONT, BACK + "Publicité pour la location de chauffe-eau"),
        (FRONT, BACK + "Learn about rental services"),
    ],
)
def test_rental_mentions_outside_billed_charges_do_not_change_facts(front, back):
    assert parser(front, back).parse(b"synthetic") == parser().parse(b"synthetic")


def test_synthetic_pdf_account_note_with_rental_word_is_supported(tmp_path):
    content = create_synthetic_energir_statement(
        tmp_path / "synthetic-energir.pdf", front_note="ABC Location"
    ).read_bytes()
    assert expense_source_registry.detect(content).parser(content).amount == Decimal("114.98")


def test_multiple_bills_unreadable_pdf_and_unsupported_identity():
    for pages in ([FRONT, BACK, "Extra page"], [FRONT + FRONT, BACK]):
        with pytest.raises(ValidationError, match="manual entry"):
            EnergirParser(lambda content, pages=pages: pages).parse(b"synthetic")
    for content in (b"", b"not a PDF"):
        assert not EnergirParser().detects(content)
        with pytest.raises(ValidationError) as error:
            EnergirParser().parse(content)
        assert error.value.code == "expense_energir_unreadable"
    with pytest.raises(ValidationError) as error:
        parser(FRONT.replace("Énergir", "Other provider")).parse(b"synthetic")
    assert error.value.code == "expense_energir_format"
    assert not EnergirParser(lambda content: ["", " "]).detects(b"synthetic")
