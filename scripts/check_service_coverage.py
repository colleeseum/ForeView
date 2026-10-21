# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Reject silent loss of executed coverage for capability-grouped services."""

from __future__ import annotations

import ast
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path


def check_implementation_coverage(
    root: Path, report: Path, implementations: Iterable[Path], label: str
) -> int:
    classes = {
        item.attrib["filename"]: item
        for item in ET.parse(report).iter("class")  # nosec B314 - local coverage output
    }
    count = 0
    for path in implementations:
        count += 1
        relative = path.relative_to(root).as_posix()
        item = classes.get(relative)
        if item is None:
            raise ValueError(f"{label} missing coverage: {relative}")
        lines = list(item.iter("line"))
        executed = {int(line.attrib["number"]) for line in lines if int(line.attrib["hits"]) > 0}
        functions = [
            node
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not any(
            any(
                node.body[0].lineno <= line <= (node.end_lineno or node.lineno) for line in executed
            )
            for node in functions
        ):
            raise ValueError(f"{label} has no executed function body: {relative}")
        branches = [line for line in lines if line.attrib.get("branch") == "true"]
        if branches and not any(
            int(line.attrib["condition-coverage"].split("(")[1].split("/")[0]) > 0
            for line in branches
        ):
            raise ValueError(f"{label} has no executed branch: {relative}")
    return count


def check_service_coverage(root: Path, report: Path) -> int:
    implementations = sorted(
        path
        for path in (root / "services").rglob("*.py")
        if path.parent != root / "services" and path.name != "__init__.py"
    )
    if not implementations:
        raise ValueError("No capability-grouped service implementations found")
    return check_implementation_coverage(root, report, implementations, "Service")


if __name__ == "__main__":
    count = check_service_coverage(Path.cwd(), Path(sys.argv[1]))
    print(f"Verified executed function/branch coverage for {count} grouped service modules.")
