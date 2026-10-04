# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

import sqlite3


class ClosingConnection(sqlite3.Connection):
    """SQLite connection whose outer context manager also closes the handle."""

    def __enter__(self) -> ClosingConnection:
        self._context_depth = getattr(self, "_context_depth", 0) + 1
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self._context_depth -= 1
            if self._context_depth == 0:
                self.close()
