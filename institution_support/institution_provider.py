# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Identity and optional capabilities of one financial institution."""

from __future__ import annotations

from dataclasses import dataclass

from institution_support.connection_capability import ConnectionCapability
from institution_support.csv_parser import CsvParser
from institution_support.document_importer import DocumentImporter
from institution_support.help_topic import HelpTopic
from institution_support.transaction_repair import TransactionRepair


@dataclass(frozen=True)
class InstitutionProvider:
    """Identity and optional capabilities for one financial institution."""

    key: str
    display_name: str
    version: str = "2026.09.29"
    aliases: tuple[str, ...] = ()
    importers: tuple[DocumentImporter, ...] = ()
    connection: ConnectionCapability | None = None
    help_topics: tuple[HelpTopic, ...] = ()
    # Accounts hold securities, so cash left uninvested is worth flagging.
    holds_securities: bool = False
    # Raw-row source tags whose rows carry a statement-printed balance.
    statement_sources: tuple[str, ...] = ()
    csv_parser: CsvParser | None = None
    balance_excluded_sources: tuple[str, ...] = ()
    balance_including_snapshot_sources: tuple[str, ...] = ()
    transaction_repair: TransactionRepair | None = None

    def names(self) -> tuple[str, ...]:
        return (self.key, self.display_name, *self.aliases)
