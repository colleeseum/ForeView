from __future__ import annotations

import io
import re
from decimal import Decimal

import pdfplumber

from .errors import RuleSourceFormatError
from .parsing import decimal_value


def quebec_tax_inputs_from_pdf(
    content: bytes, source_id: str
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    try:
        with pdfplumber.open(io.BytesIO(content)) as document:
            text = "\n".join((page.extract_text() or "") for page in document.pages[:15])
    except Exception as error:
        raise RuleSourceFormatError(f"Could not read Quebec tax guide {source_id}") from error
    basic = re.search(r"Basic personal amount\s+\$?([\d, ]+)", text, flags=re.I)
    worker = re.search(r"maximum deduction for workers is\s+\$?([\d, ]+)", text, flags=re.I)
    worker_rate = re.search(r"Deduction for workers.*?0\.0(\d+)\s*[×x]", text, flags=re.I | re.S)
    qpp_base_rate = re.search(r"base contribution rate of\s+([\d.]+)%", text, flags=re.I)
    if basic is None or worker is None or worker_rate is None or qpp_base_rate is None:
        raise RuleSourceFormatError(f"Could not find required Quebec tax inputs in {source_id}")
    return (
        decimal_value(basic.group(1)),
        decimal_value(worker.group(1)),
        Decimal(f"0.0{worker_rate.group(1)}"),
        Decimal(qpp_base_rate.group(1)) / Decimal("100"),
    )
