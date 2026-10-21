# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Verify relocated synthetic implementations remain instrumented and exercised."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__:
    from .check_service_coverage import check_implementation_coverage
else:
    from check_service_coverage import check_implementation_coverage


def check_synthetic_coverage(root: Path, report: Path) -> int:
    implementations = [
        root / "devtools" / "synthetic" / f"synthetic_{name}.py"
        for name in ("documents", "expenses", "questrade", "runtime")
    ]
    return check_implementation_coverage(root, report, implementations, "Synthetic tool")


if __name__ == "__main__":
    count = check_synthetic_coverage(Path.cwd(), Path(sys.argv[1]))
    print(f"Verified executed function/branch coverage for {count} synthetic tool modules.")
