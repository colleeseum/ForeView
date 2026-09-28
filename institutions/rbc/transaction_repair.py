"""Repair transaction rows produced by superseded RBC parsers."""

from __future__ import annotations

from repositories.transaction_repository import TransactionRepository

from .raw_sources import RBC_TFSA_PDF

_DESCRIPTIONS = {
    "Intérêtsréinvesti": "Interest reinvested",
    "IntérêtsCPGversésàl'épargne": "GIC interest paid to savings",
}


def repair_transactions(transactions: TransactionRepository) -> int:
    rows = transactions.descriptions_from_source(RBC_TFSA_PDF)
    for transaction_id, description, _raw_data in rows:
        transactions.classify(
            transaction_id,
            description=_DESCRIPTIONS.get(description or "", description),
            category="Interest",
            transaction_type="interest",
        )
    return len(rows)
