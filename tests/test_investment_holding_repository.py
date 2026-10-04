# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.investment_holding_repository import InvestmentHoldingRepository
from tests.support import create_account, ensure_domain_schema


class InvestmentHoldingRepositoryTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    @staticmethod
    def _account(connection: sqlite3.Connection) -> int:
        return create_account(connection, "Brokerage", "tfsa", account_number="BROKER-001")

    @staticmethod
    def _upsert(
        repository: InvestmentHoldingRepository,
        account_id: int,
        *,
        source_filename: str = "statement.pdf",
        market_value: float = 1250.0,
        fund_code: str = "FUND",
    ):
        return repository.upsert(
            account_id,
            "2026-09-27",
            "Equity",
            fund_code,
            "Example Fund",
            10.0,
            125.0,
            market_value,
            50.0,
            source_filename,
        )

    def test_upsert_and_retrieve_immutable_complete_row(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = InvestmentHoldingRepository(connection)

            holding = self._upsert(repository, account)

            self.assertEqual(holding.account_id, account)
            self.assertEqual(holding.fund_code, "FUND")
            self.assertEqual(holding.units, 10.0)
            self.assertEqual(holding.unit_price, 125.0)
            self.assertEqual(holding.market_value, 1250.0)
            self.assertEqual(holding.allocation_pct, 50.0)
            self.assertEqual(repository.get(holding.id), holding)
            self.assertEqual(repository.list_for_account(account), [holding])
            self.assertIsNone(repository.get(None))
            self.assertIsNone(repository.get(999))
            with self.assertRaises(FrozenInstanceError):
                holding.market_value = 0  # type: ignore[misc]

    def test_upsert_replaces_same_source_key(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = InvestmentHoldingRepository(connection)
            original = self._upsert(repository, account, market_value=1250.0)

            replacement = self._upsert(repository, account, market_value=1500.0)

            holdings = repository.list_for_account(account)
            self.assertEqual(len(holdings), 1)
            self.assertEqual(holdings[0], replacement)
            self.assertEqual(replacement.market_value, 1500.0)
            self.assertNotEqual(replacement.id, original.id)

    def test_same_fund_and_date_from_different_sources_are_distinct(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = InvestmentHoldingRepository(connection)
            self._upsert(repository, account, source_filename="first.pdf")
            self._upsert(repository, account, source_filename="second.pdf")

            self.assertEqual(len(repository.list_for_account(account)), 2)

    def test_delete_for_account_date_preserves_other_dates(self):
        with self._connection() as connection:
            account = self._account(connection)
            repository = InvestmentHoldingRepository(connection)
            self._upsert(repository, account)
            repository.upsert(
                account,
                "2026-09-28",
                None,
                "OTHER",
                "Other Fund",
                1,
                1,
                1,
                None,
                "other.pdf",
            )

            repository.delete_for_account_date(account, "2026-09-27")

            holdings = repository.list_for_account(account)
            self.assertEqual([holding.valuation_date for holding in holdings], ["2026-09-28"])
            self.assertIsNone(holdings[0].asset_class)
            self.assertIsNone(holdings[0].allocation_pct)

    def test_delete_source_prefix_is_scoped_to_account(self):
        with self._connection() as connection:
            first_account = self._account(connection)
            second_account = create_account(
                connection, "Other brokerage", "tfsa", account_number="BROKER-002"
            )
            repository = InvestmentHoldingRepository(connection)
            self._upsert(repository, first_account, source_filename="questrade:first")
            self._upsert(
                repository,
                first_account,
                source_filename="statement.pdf",
                fund_code="MANUAL",
            )
            self._upsert(repository, second_account, source_filename="questrade:second")

            repository.delete_for_account_source_prefix(first_account, "questrade:")

            self.assertEqual(
                [holding.fund_code for holding in repository.list_for_account(first_account)],
                ["MANUAL"],
            )
            self.assertEqual(len(repository.list_for_account(second_account)), 1)

    def test_negative_values_remain_permitted_by_existing_schema(self):
        with self._connection() as connection:
            account = self._account(connection)
            holding = InvestmentHoldingRepository(connection).upsert(
                account,
                "not-a-date",
                "Unknown",
                "SHORT",
                "Short position",
                -2,
                -10,
                -20,
                -1,
                "source",
            )

            self.assertEqual(holding.units, -2)
            self.assertEqual(holding.market_value, -20)

    def test_latest_returns_newest_valuation_per_fund_with_filters(self):
        with self._connection() as connection:
            repository = InvestmentHoldingRepository(connection)
            tfsa = self._account(connection)
            rrsp = create_account(connection, "Pension", "rrsp", account_number="RRSP-001")
            self._upsert(repository, tfsa, market_value=100.0)
            repository.upsert(
                tfsa, "2026-10-01", "Equity", "FUND", "Example Fund", 10, 13, 130.0, None, "later"
            )
            self._upsert(repository, rrsp, market_value=500.0, fund_code="BOND")

            everything = repository.latest()
            by_account = repository.latest(account_id=tfsa)
            by_type = repository.latest(account_type="rrsp")
            both = repository.latest(account_id=tfsa, account_type="rrsp")

            self.assertEqual(
                sorted((row["fund_code"], row["market_value"]) for row in everything),
                [("BOND", 500.0), ("FUND", 130.0)],
            )
            self.assertEqual([row["valuation_date"] for row in by_account], ["2026-10-01"])
            self.assertEqual([row["account_name"] for row in by_type], ["Pension"])
            self.assertEqual(both, [])
