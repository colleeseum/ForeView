# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Development tool relocation preserves CLI behavior and isolation from production."""

import ast
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from scripts.check_synthetic_coverage import check_synthetic_coverage

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("documents", "expenses", "questrade", "runtime")


def run_tool(cwd: Path, name: str, *args: str) -> subprocess.CompletedProcess[str]:
    # The checkout is explicitly importable while cwd/destination remain independent.
    return subprocess.run(
        [sys.executable, "-m", f"devtools.synthetic.synthetic_{name}", *args],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def snapshot(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_synthetic_imports_are_non_eager_and_have_no_io(tmp_path: Path):
    code = """
import importlib
import os
import sys
sys.dont_write_bytecode = True
def audit(event, args):
    if event in ('sqlite3.connect', 'socket.connect', 'os.mkdir'):
        raise AssertionError(('Unexpected import side effect', event))
    if event == 'open':
        mode, flags = args[1:3]
        if (mode and any(c in mode for c in 'wax+')) or (
            flags and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            raise AssertionError(('Unexpected import write', args[0]))
sys.addaudithook(audit)
import devtools
import devtools.synthetic
assert not any(name.startswith('devtools.synthetic.synthetic_') for name in sys.modules)
for short in ('documents', 'expenses', 'questrade', 'runtime'):
    module = importlib.import_module('devtools.synthetic.synthetic_' + short)
    assert module.__name__ == 'devtools.synthetic.synthetic_' + short
    assert importlib.util.find_spec('synthetic_' + short) is None
print('IMPORTS_SAFE')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "IMPORTS_SAFE" in result.stdout
    assert not list(tmp_path.iterdir())


def test_synthetic_cli_resource_roots_and_repeated_loads(tmp_path: Path):
    # Relative destinations still resolve against the caller's cwd, not the tool package.
    result = run_tool(tmp_path, "runtime", "invented")
    assert result.returncode == 0, result.stdout + result.stderr
    target = tmp_path / "invented"
    assert str(target / "finance.sqlite3") in result.stdout
    with closing(sqlite3.connect(target / "finance.sqlite3")) as connection:
        assert connection.execute("SELECT COUNT(*) FROM public_rule_approvals").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM expense_records").fetchone()[0] == 7

    expenses = run_tool(tmp_path, "expenses", str(target))
    assert expenses.returncode == 0, expenses.stdout + expenses.stderr
    assert "Created 0 synthetic expense records" in expenses.stdout

    for scenario in ("initial", "updated"):
        first = run_tool(tmp_path, "questrade", "invented", "--scenario", scenario)
        assert first.returncode == 0, first.stdout + first.stderr
        results = [json.loads(line) for line in first.stdout.splitlines()]
        assert sum(item["account_count"] for item in results) == 4
        repeated = run_tool(tmp_path, "questrade", "invented", "--scenario", scenario)
        assert repeated.returncode == 0, repeated.stdout + repeated.stderr
        assert (
            sum(json.loads(line)["transaction_count"] for line in repeated.stdout.splitlines()) == 0
        )

    before = snapshot(target)
    refused = run_tool(tmp_path, "runtime", "invented")
    assert refused.returncode != 0
    assert "already exists" in refused.stderr
    assert snapshot(target) == before


@pytest.mark.parametrize("tool", ["expenses", "questrade"])
def test_loader_clis_reject_private_runtime_without_writes(tmp_path: Path, tool: str):
    target = tmp_path / "private"
    target.mkdir()
    (target / "finance.config.json").write_text('{"RUNTIME_ENVIRONMENT": "private"}')
    (target / "finance.sqlite3").write_bytes(b"untouched private database sentinel")
    before = snapshot(target)
    result = run_tool(tmp_path, tool, str(target))
    assert result.returncode != 0
    assert "non-synthetic runtime" in result.stderr
    assert snapshot(target) == before


@pytest.mark.parametrize("existing", ["finance.sqlite3", "finance.config.json"])
def test_runtime_cli_rejects_either_existing_file_without_writes(tmp_path: Path, existing: str):
    target = tmp_path / "existing"
    target.mkdir()
    (target / existing).write_bytes(b"existing runtime sentinel")
    before = snapshot(target)
    result = run_tool(tmp_path, "runtime", str(target))
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert snapshot(target) == before


def test_production_modules_do_not_import_devtools():
    roots = (
        "account_types",
        "domain",
        "expense_sources",
        "income_sources",
        "infrastructure",
        "ingestion",
        "institution_support",
        "institutions",
        "localization",
        "projection",
        "public_pension_sources",
        "repositories",
        "services",
        "tax_notices",
        "web",
    )
    paths = [ROOT / name for name in ("app.py", "runtime_backup.py", "update_public_rules.py")]
    paths.extend(path for name in roots for path in (ROOT / name).rglob("*.py"))
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(name == "devtools" or name.startswith("devtools.") for name in names), (
                path
            )
    assert all(not (ROOT / f"synthetic_{name}.py").exists() for name in TOOLS)


@pytest.mark.parametrize("failure", [None, "missing", "unexecuted", "branches"])
def test_synthetic_coverage_gate(tmp_path: Path, failure: str | None):
    package = tmp_path / "devtools" / "synthetic"
    package.mkdir(parents=True)
    elements = []
    for name in TOOLS:
        (package / f"synthetic_{name}.py").write_text(
            "def sample(value):\n    if value:\n        return value\n    return 0\n"
        )
        if failure == "missing" and name == "expenses":
            continue
        hits = 0 if failure == "unexecuted" and name == "expenses" else 1
        covered = 0 if failure == "branches" and name == "expenses" else 1
        elements.append(
            f'<class filename="devtools/synthetic/synthetic_{name}.py"><lines>'
            f'<line number="2" hits="{hits}" branch="true" '
            f'condition-coverage="50% ({covered}/2)"/></lines></class>'
        )
    report = tmp_path / "coverage.xml"
    report.write_text(f"<coverage>{''.join(elements)}</coverage>")
    if failure:
        with pytest.raises(ValueError, match="Synthetic tool"):
            check_synthetic_coverage(tmp_path, report)
    else:
        assert check_synthetic_coverage(tmp_path, report) == 4
