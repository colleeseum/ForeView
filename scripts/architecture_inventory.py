# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Read-only, reproducible ARCH-01A repository structure inventory.

Usage: python scripts/architecture_inventory.py [--json]
No third-party dependencies, network calls, imports of app modules, or runtime reads.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_IMPORT = re.compile(r"""(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)""")
TEMPLATE_ASSET = re.compile(r"""(?:src|href)\s*=\s*['"]([^'"]+\.(?:mjs|js|css)(?:\?[^'"]*)?)['"]""")
EXCLUDE = {".git", ".runtime", ".venv", "node_modules", "__pycache__"}


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [Path(part.decode("utf-8")) for part in result.stdout.split(b"\0") if part]


def import_graph(paths: list[Path]) -> tuple[dict[str, set[str]], dict[str, int]]:
    modules = {}
    for path in paths:
        if path.suffix != ".py":
            continue
        parts = path.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            modules[".".join(parts)] = path
    graph: dict[str, set[str]] = defaultdict(set)
    external: Counter[str] = Counter()
    for module, path in modules.items():
        graph[module]
        try:
            tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError):
            continue
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = ".".join(package.split(".")[:max(0, len(package.split(".")) - node.level + 1)]) if node.level else ""
                base = f"{prefix}.{node.module}" if prefix and node.module else prefix or node.module or ""
                names = [base] + [f"{base}.{alias.name}" for alias in node.names] if base else []
            for name in names:
                target = name
                while target and target not in modules:
                    target = target.rpartition(".")[0]
                if target and target != module:
                    graph[module].add(target)
                elif not target and name:
                    external[name.split(".")[0]] += 1
    return graph, dict(external)


def cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan strongly connected components, excluding singleton nodes."""
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indexes: dict[str, int] = {}
    low: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for neighbor in sorted(graph[node]):
            if neighbor not in indexes:
                visit(neighbor)
                low[node] = min(low[node], low[neighbor])
            elif neighbor in on_stack:
                low[node] = min(low[node], indexes[neighbor])
        if low[node] == indexes[node]:
            component = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(graph):
        if node not in indexes:
            visit(node)
    return sorted(components, key=lambda c: (-len(c), c))


def inventory() -> dict:
    paths = [p for p in tracked_paths() if not (set(p.parts) & EXCLUDE)]
    by_directory: dict[str, dict] = defaultdict(lambda: {"files": 0, "bytes": 0, "types": Counter()})
    for path in paths:
        if not (ROOT / path).is_file():
            continue
        key = path.parts[0] if len(path.parts) > 1 else "(root)"
        item = by_directory[key]
        item["files"] += 1
        item["bytes"] += (ROOT / path).stat().st_size
        item["types"][path.suffix or "(none)"] += 1
    graph, external = import_graph(paths)
    incoming: Counter[str] = Counter()
    for neighbors in graph.values():
        incoming.update(neighbors)
    js_edges = {}
    for path in paths:
        if path.suffix in {".mjs", ".js"}:
            js_edges[path.as_posix()] = sorted(
                {a or b for a, b in JS_IMPORT.findall((ROOT / path).read_text(encoding="utf-8"))}
            )
    assets = {}
    for path in paths:
        if path.suffix in {".html", ".jinja", ".jinja2"}:
            assets[path.as_posix()] = sorted(
                set(TEMPLATE_ASSET.findall((ROOT / path).read_text(encoding="utf-8")))
            )
    return {
        "tracked_files": len(paths),
        "top_level": {
            key: {"files": value["files"], "bytes": value["bytes"],
                  "types": dict(sorted(value["types"].items()))}
            for key, value in sorted(by_directory.items())
        },
        "python": {
            "modules": len(graph),
            "edges": sum(map(len, graph.values())),
            "cycles": cycles(graph),
            "most_imported": incoming.most_common(25),
            "cross_package_edges": sorted(
                [f"{src} -> {dst}" for src, deps in graph.items() for dst in deps
                 if src.split(".")[0] != dst.split(".")[0]]
            ),
            "unresolved_import_roots": dict(sorted(external.items())),
        },
        "javascript": {"files": len(js_edges), "imports": js_edges},
        "template_assets": assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable inventory")
    args = parser.parse_args()
    data = inventory()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print(f"Tracked files: {data['tracked_files']}")
    print("Top-level paths (files / bytes):")
    for key, info in data["top_level"].items():
        print(f"  {key:30s} {info['files']:4d}  {info['bytes']:9d}")
    py = data["python"]
    print(f"Python modules: {py['modules']}; resolved import edges: {py['edges']}")
    print(f"Python strongly connected components (>1 module): {len(py['cycles'])}")
    for component in py["cycles"][:10]:
        print("  cycle:", ", ".join(component))
    print("Most imported Python modules:")
    for module, count in py["most_imported"][:15]:
        print(f"  {count:4d}  {module}")
    print(f"JavaScript modules: {data['javascript']['files']}")
    print("For full edges and template assets use --json.")


if __name__ == "__main__":
    main()
