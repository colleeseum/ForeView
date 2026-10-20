# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Coverage thresholds must not hide unmeasured relocated services."""

from pathlib import Path

import pytest

from scripts.check_service_coverage import check_service_coverage


@pytest.mark.parametrize("failure", [None, "missing", "unexecuted", "branches"])
def test_service_coverage_gate_rejects_missing_execution(tmp_path: Path, failure: str | None):
    package = tmp_path / "services" / "accounts"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Non-eager package."""', encoding="utf-8")
    (package / "summary.py").write_text(
        "def summary(value):\n    if value:\n        return value\n    return 0\n", encoding="utf-8"
    )
    hits = 0 if failure == "unexecuted" else 1
    covered = 0 if failure == "branches" else 1
    element = f'<class filename="services/accounts/summary.py"><lines><line number="2" hits="{hits}" branch="true" condition-coverage="50% ({covered}/2)"/></lines></class>'
    report = tmp_path / "coverage.xml"
    report.write_text(
        f"<coverage>{'' if failure == 'missing' else element}</coverage>", encoding="utf-8"
    )
    if failure:
        with pytest.raises(ValueError, match="Service"):
            check_service_coverage(tmp_path, report)
    else:
        assert check_service_coverage(tmp_path, report) == 1


def test_service_coverage_gate_requires_implementations(tmp_path: Path):
    report = tmp_path / "coverage.xml"
    report.write_text("<coverage/>", encoding="utf-8")
    with pytest.raises(ValueError, match="No capability-grouped"):
        check_service_coverage(tmp_path, report)
