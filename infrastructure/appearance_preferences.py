# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Per-runtime presentation preferences, independent of financial records."""

import json
import os
import tempfile
from pathlib import Path

APPEARANCE_FILENAME = "appearance.json"


class AppearancePreferences:
    text_sizes = ("small", "normal", "large")
    default_text_size = "small"

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / APPEARANCE_FILENAME

    def text_size(self) -> str:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8")).get("text_size")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return self.default_text_size
        return (
            value if isinstance(value, str) and value in self.text_sizes else self.default_text_size
        )

    def select_text_size(self, value: str) -> None:
        if value not in self.text_sizes:
            raise ValueError("Unsupported text size")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".appearance.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(json.dumps({"text_size": value}) + "\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
