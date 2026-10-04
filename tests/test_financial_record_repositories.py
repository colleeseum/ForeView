# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import app as application
from domain.parsed_tax_value import ParsedTaxValue
from infrastructure.runtime_config import RuntimeConfig
from repositories.annual_tax_assessment_repository import AnnualTaxAssessmentRepository
from repositories.annual_tax_value_repository import AnnualTaxValueRepository
from repositories.person_repository import PersonRepository
from repositories.public_pension_statement_repository import PublicPensionStatementRepository
from repositories.registered_plan_room_repository import RegisteredPlanRoomRepository


class FinancialRecordRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        runtime = RuntimeConfig(Path(self.directory.name))
        application.initialize(runtime)
        self.connection = runtime.connect()
        self.addCleanup(self.connection.close)
        self.person_id = PersonRepository(self.connection).create("Alex Example").id

    def test_assessment_and_rrsp_room_are_independent_records(self) -> None:
        assessment = AnnualTaxAssessmentRepository(self.connection).upsert(
            self.person_id,
            2025,
            "CA",
            "2026-05-11",
            total_income="223074",
            net_income="214510",
            taxable_income="214510",
            net_tax="43995.95",
            tax_withheld="47010.24",
            balance="-10273.62",
            source="CRA NOA",
            source_version="2026.09.29",
            document_hash="abc",
        )
        room = RegisteredPlanRoomRepository(self.connection).upsert(
            self.person_id,
            "RRSP",
            2026,
            "2026-05-11",
            deduction_limit="58810",
            unused_deduction_room="25000",
            new_room="33810",
            unused_contributions="0",
            available_room="58810",
            source="CRA NOA",
            source_version="2026.09.29",
        )

        self.assertEqual(assessment.net_tax, Decimal("43995.95"))
        self.assertEqual(assessment.balance, Decimal("-10273.62"))
        self.assertEqual(room.available_room, Decimal("58810.00"))

    def test_public_pension_statement_replaces_children_atomically(self) -> None:
        repository = PublicPensionStatementRepository(self.connection)
        statement = repository.upsert(
            self.person_id,
            "2026-06-15",
            "QPP",
            True,
            "2026.09.29",
            "hash",
            ((2025, Decimal("0"), Decimal("81200"), "A"),),
            (("continue", 65, Decimal("1435")), ("stop", 65, Decimal("1012"))),
        )

        self.assertTrue(statement.excludes_second_enhancement)
        self.assertEqual(repository.earnings(statement.id)[0].cpp_earnings, Decimal("81200.00"))
        self.assertEqual(len(repository.estimates(statement.id)), 2)

    def test_tax_document_values_preserve_reported_and_determined_concepts(self) -> None:
        repository = AnnualTaxValueRepository(self.connection)
        values = repository.replace_document(
            self.person_id,
            2025,
            "assessment",
            "CA-QC",
            "Revenu Quebec NOA",
            "2026.09.29.1",
            "hash",
            (
                ParsedTaxValue(
                    "interest_investment_income",
                    "Interest and other investment income",
                    Decimal("3900"),
                    Decimal("3925.26"),
                    "130",
                    2025,
                ),
                ParsedTaxValue(
                    "canada_training_credit_limit",
                    "Canada training credit limit",
                    None,
                    Decimal("250"),
                    effective_year=2026,
                ),
            ),
        )

        self.assertEqual(len(values), 2)
        interest = next(item for item in values if item.concept == "interest_investment_income")
        self.assertEqual(interest.reported_amount, Decimal("3900.00"))
        self.assertEqual(interest.determined_amount, Decimal("3925.26"))
        self.assertEqual(
            repository.get(
                self.person_id,
                2025,
                "assessment",
                "CA-QC",
                "canada_training_credit_limit",
                2026,
            ).determined_amount,
            Decimal("250.00"),
        )

        replaced = repository.replace_document(
            self.person_id,
            2025,
            "assessment",
            "CA-QC",
            "Revenu Quebec NOA",
            "2026.09.29.1",
            "new-hash",
            (
                ParsedTaxValue(
                    "interest_investment_income",
                    "Interest and other investment income",
                    Decimal("3925.26"),
                    Decimal("3925.26"),
                    "130",
                    2025,
                ),
            ),
        )
        self.assertEqual(len(replaced), 1)
        self.assertEqual(replaced[0].reported_amount, Decimal("3925.26"))
        self.assertIsNone(
            repository.get(
                self.person_id,
                2025,
                "assessment",
                "CA-QC",
                "canada_training_credit_limit",
                2026,
            )
        )


if __name__ == "__main__":
    unittest.main()
