"""Reading PDF statements into page text."""

from __future__ import annotations

import io
from collections.abc import Callable, Iterable
from typing import Any, Protocol

import pdfplumber

from ingestion.pdf_page import PdfPage


class PdfDocument(Protocol):
    pages: Iterable[PdfPage]

    def __enter__(self) -> PdfDocument: ...

    def __exit__(self, *args: object) -> bool | None: ...


PdfOpener = Callable[[io.BytesIO], PdfDocument]


def open_pdf(source: io.BytesIO) -> Any:
    # pdfplumber's document type is structurally a PdfDocument but not declared as one.
    return pdfplumber.open(source)


def pdf_page_texts(pdf_opener: PdfOpener, content: bytes) -> list[str]:
    with pdf_opener(io.BytesIO(content)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]
