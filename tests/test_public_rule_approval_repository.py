# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError

from repositories.public_rule_approval_repository import PublicRuleApprovalRepository
from tests.support import ensure_domain_schema


class PublicRuleApprovalRepositoryTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        ensure_domain_schema(connection)
        return closing(connection)

    def test_approval_is_bound_to_exact_rule_set_hash(self):
        with self._connection() as connection:
            repository = PublicRuleApprovalRepository(connection)
            first_hash = "a" * 64
            changed_hash = "b" * 64

            approval = repository.approve("ca-2026-official", first_hash)

            self.assertEqual(repository.get("ca-2026-official", first_hash), approval)
            self.assertIsNone(repository.get("ca-2026-official", changed_hash))
            with self.assertRaises(FrozenInstanceError):
                approval.content_hash = changed_hash  # type: ignore[misc]

    def test_repeated_approval_is_idempotent(self):
        with self._connection() as connection:
            repository = PublicRuleApprovalRepository(connection)
            content_hash = "c" * 64
            first = repository.approve("ca-qc-2026-official", content_hash)
            second = repository.approve("ca-qc-2026-official", content_hash)

            self.assertEqual(second, first)
            count = connection.execute("SELECT COUNT(*) FROM public_rule_approvals").fetchone()[0]
            self.assertEqual(count, 1)
