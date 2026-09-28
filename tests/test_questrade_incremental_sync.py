"""Questrade activity is fetched from where the previous sync stopped."""

from __future__ import annotations

import tempfile
import unittest
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from infrastructure.runtime_config import RuntimeConfig
from institutions.questrade.sync import (
    DEFAULT_HISTORY,
    LOOKBACK,
    WINDOW,
    sync_questrade_connection,
)
from repositories.activity_sync_state_repository import ActivitySyncStateRepository
from repositories.questrade_authorization_repository import QuestradeAuthorizationRepository
from tests.support import ensure_domain_schema


class IncrementalActivitySyncTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.runtime = RuntimeConfig(Path(directory.name))
        with self.runtime.connect() as connection:
            ensure_domain_schema(connection)
            QuestradeAuthorizationRepository(connection).add_if_absent(
                "alex",
                access_token="unused",
                refresh_token="unused",
                api_server="https://api01.iq.questrade.com/",
            )
        self.windows: list[tuple[datetime, datetime]] = []
        self.fail_activities = False
        self.fail_accounts = False
        self.fail_positions = False

    def _api(self, _authorization, path: str):
        if path == "/v1/accounts":
            if self.fail_accounts:
                raise RuntimeError("Questrade accounts failed (500)")
            return {"accounts": [{"number": "QT-1", "type": "TFSA"}]}
        if "/positions" in path and self.fail_positions:
            raise RuntimeError("Questrade positions failed (500)")
        if "/activities?" in path:
            if self.fail_activities:
                raise RuntimeError("Questrade API request failed (500)")
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
            self.windows.append(
                (
                    datetime.fromisoformat(query["startTime"][0]),
                    datetime.fromisoformat(query["endTime"][0]),
                )
            )
            return {"activities": []}
        return {}

    def _sync(self, history_start=None, fetch_from=None):
        self.windows = []
        return sync_questrade_connection(
            self.runtime.connect,
            "alex",
            api_getter=self._api,
            refresh_expiring=lambda _connection: None,
            refresh_authorization=lambda _connection, _authorization: None,
            history_start=history_start,
            fetch_from=fetch_from,
        )

    def _watermark(self):
        with self.runtime.connect() as connection:
            return ActivitySyncStateRepository(connection).synced_until(1)

    def test_first_sync_starts_at_history_start_in_windows_within_the_api_limit(self):
        self._sync(history_start="2024-01-15")

        self.assertEqual(self.windows[0][0], datetime(2024, 1, 15, tzinfo=UTC))
        for (_start, end), (next_start, _) in zip(self.windows, self.windows[1:], strict=False):
            self.assertEqual(end, next_start)
        self.assertTrue(all(end - start <= timedelta(days=31) for start, end in self.windows))
        self.assertEqual(self.windows[-1][1], self._watermark())

    def test_a_recent_previous_sync_rereads_one_full_window(self):
        self._sync(history_start="2024-01-15")

        self._sync(history_start="2024-01-15")

        [(start, end)] = self.windows
        self.assertEqual(end - start, WINDOW)

    def test_an_old_previous_sync_rereads_the_minimum_lookback(self):
        self._sync(history_start="2024-01-15")
        long_ago = datetime.now(UTC) - timedelta(days=60)
        with self.runtime.connect() as connection:
            ActivitySyncStateRepository(connection).record(1, long_ago)
            connection.commit()

        self._sync(history_start="2024-01-15")

        self.assertEqual(self.windows[0][0], long_ago - LOOKBACK)
        self.assertEqual(len(self.windows), 3)
        self.assertGreater(self._watermark(), long_ago)

    def test_without_history_start_the_first_sync_uses_the_default_depth(self):
        before = datetime.now(UTC)

        self._sync()

        reach = before - self.windows[0][0]
        self.assertAlmostEqual(reach.total_seconds(), DEFAULT_HISTORY.total_seconds(), delta=60)

    def test_failed_activity_fetch_keeps_the_watermark(self):
        self._sync(history_start="2024-01-15")
        watermark = self._watermark()
        with self.runtime.connect() as connection:
            successful_sync = QuestradeAuthorizationRepository(connection).get_by_name("alex")
        self.assertIsNotNone(successful_sync)

        self.fail_activities = True
        result = self._sync(history_start="2024-01-15")

        self.assertEqual(self._watermark(), watermark)
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["synced_at"])
        self.assertEqual(result["errors"][0]["component"], "activities")
        with self.runtime.connect() as connection:
            failed_sync = QuestradeAuthorizationRepository(connection).get_by_name("alex")
        self.assertIsNotNone(failed_sync)
        self.assertEqual(failed_sync.last_sync_at, successful_sync.last_sync_at)
        self.assertIsNotNone(failed_sync.last_sync_attempt_at)
        self.assertIn("activities", failed_sync.last_sync_error)

    def test_position_failure_does_not_prevent_activity_sync(self):
        self.fail_positions = True

        result = self._sync(history_start="2026-09-01")

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["errors"][0]["component"], "positions")
        self.assertTrue(self.windows)
        self.assertEqual(self.windows[-1][1], self._watermark())

    def test_fatal_account_discovery_failure_records_the_attempt(self):
        self.fail_accounts = True

        with self.assertRaisesRegex(RuntimeError, "accounts failed"):
            self._sync()

        with self.runtime.connect() as connection:
            authorization = QuestradeAuthorizationRepository(connection).get_by_name("alex")
        self.assertIsNotNone(authorization)
        self.assertIsNotNone(authorization.last_sync_attempt_at)
        self.assertIsNone(authorization.last_sync_at)
        self.assertIn("accounts failed", authorization.last_sync_error)

    def test_fetch_from_refetches_history_regardless_of_the_previous_sync(self):
        self._sync(history_start="2026-01-01")

        self._sync(history_start="2026-01-01", fetch_from="2025-06-01")

        self.assertEqual(self.windows[0][0], datetime(2025, 6, 1, tzinfo=UTC))
        self.assertGreater(len(self.windows), 1)

    def test_invalid_fetch_from_is_reported_clearly(self):
        with self.assertRaisesRegex(RuntimeError, "fetch_from must be a YYYY-MM-DD date"):
            self._sync(fetch_from="June 1")

    def test_invalid_history_start_is_reported_clearly(self):
        with self.assertRaisesRegex(RuntimeError, "history_start must be a YYYY-MM-DD date"):
            self._sync(history_start="15/01/2024")


if __name__ == "__main__":
    unittest.main()
