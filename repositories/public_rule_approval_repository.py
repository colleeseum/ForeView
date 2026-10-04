# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Persistence for local approvals of exact public-rule hashes."""

from __future__ import annotations

import sqlite3

from domain.public_rule_approval import PublicRuleApproval


class PublicRuleApprovalRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def approve(self, rule_set_id: str, content_hash: str) -> PublicRuleApproval:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO public_rule_approvals(rule_set_id, content_hash)
            VALUES (?, ?)
            """,
            (rule_set_id, content_hash),
        )
        approval = self.get(rule_set_id, content_hash)
        if approval is None:  # pragma: no cover - SQLite insert/select invariant
            raise RuntimeError("Approved public rule could not be retrieved")
        return approval

    def get(self, rule_set_id: str, content_hash: str) -> PublicRuleApproval | None:
        row = self._connection.execute(
            """
            SELECT rule_set_id, content_hash, approved_at
            FROM public_rule_approvals
            WHERE rule_set_id = ? AND content_hash = ?
            """,
            (rule_set_id, content_hash),
        ).fetchone()
        if row is None:
            return None
        return PublicRuleApproval(
            rule_set_id=str(row[0]), content_hash=str(row[1]), approved_at=str(row[2])
        )
