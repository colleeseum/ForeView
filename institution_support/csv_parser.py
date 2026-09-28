from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ingestion.csv_format import CsvTransactionRow

CsvParser = Callable[[bytes, str | None, str], list["CsvTransactionRow"] | None]
