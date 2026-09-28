"""Read and identify RBC PDF document variants."""

from __future__ import annotations

import io
from collections.abc import Callable

from ingestion.pdf_document import PdfOpener

DepositTextParser = Callable[[str, str], dict[str, object]]


class RbcDocumentInspector:
    def __init__(self, *, pdf_opener: PdfOpener, deposit_parser: DepositTextParser) -> None:
        self._pdf_opener = pdf_opener
        self._deposit_parser = deposit_parser

    def parse_deposit_summary(
        self, content: bytes, filename: str = "statement.pdf"
    ) -> dict[str, object]:
        with self._pdf_opener(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return self._deposit_parser(text, filename)

    def is_deposit_statement(self, content: bytes) -> bool:
        try:
            with self._pdf_opener(io.BytesIO(content)) as pdf:
                pages = list(pdf.pages)
                text = "\n".join((page.extract_text() or "")[:1000] for page in pages[:1])
            return ("Personal Deposit Account" in text and "Account Summary" in text) or (
                "Compte de dépôt de particulier" in text and "Sommaire du compte" in text
            )
        except Exception:
            return False

    def is_tfsa_document(self, content: bytes) -> bool:
        try:
            with self._pdf_opener(io.BytesIO(content)) as pdf:
                pages = list(pdf.pages)
                text = "\n".join(page.extract_text() or "" for page in pages[:2])
            return (
                "Compte d'épargne libre d'impôt" in text
                and ("Votre relevé de placements" in text or "Avis d’échéance de CPG" in text)
            ) or ("GIC Maturity Notice" in text and "Tax-Free Savings Account" in text)
        except Exception:
            return False
