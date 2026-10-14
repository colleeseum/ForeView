# ARCH-01A evidence method

This is a time-bounded inventory of tracked Git blobs at `cba77584e68084ccbaf3ac068e59bed3bff4add7`.
It is not a runtime scanner, a permanent architecture gate, or ownership verification.
The script below uses only the Python standard library and read-only Git commands.
Run it from the repository root with the baseline revision as its first argument.
It prints JSON containing CSV inventory, dependency edges and a summary; it writes no files.

Extract the Python fence into a temporary file and run:

```sh
.venv/bin/python /path/to/extracted-inventory.py cba77584e68084ccbaf3ac068e59bed3bff4add7
```

## Definitions and limits

- Byte counts come from Git blobs, not filesystem blocks or compressed object sizes.
- Text lines include comments and blanks; PDF and NUL-containing blobs report zero, not source LOC.
- Directory counts are recursive at the first path component; root files have their own bucket.
- Responsibility is the existing directory boundary. There is no tracked CODEOWNERS file and
  no individual maintainer assignment is inferred.
- Rights evidence records explicit SPDX notices, public/generated provenance or missing per-file
  attribution. It does not transfer ownership or relabel third-party/government material.
- Python nodes include package initializers, CLI/synthetic tools and tests. Production excludes
  only the `tests` package. Edges are explicit imports resolved to tracked modules. An imported
  symbol is resolved to a same-named module when present, otherwise to its defining import module.
- Module, deferred function-body and TYPE_CHECKING imports are tagged separately. Function
  annotations/decorators are conservatively tagged with the enclosing function. Implicit package
  initializer execution and dynamic import targets are not modeled as graph edges.
- Both module-only and conservative all-scope production graphs are checked for strongly connected
  components. A clean static graph is not proof against runtime discovery/initialization cycles.
- JavaScript matching covers multiline literal imports, re-exports and quoted dynamic imports,
  stripping query suffixes for file lookup. Computed/backtick dynamic import expressions and
  arbitrary URL-building code require manual inspection. No full JavaScript parser is introduced.
- Flask static references include stylesheets and scripts supplied through literal
  `url_for('static', filename=...)` calls. Jinja includes and JSON catalog loading are separate
  path-sensitive concerns, not module dependencies.
- Coupling means distinct in-repository importers/targets, not call frequency, performance,
  cohesion quality or runtime object dependencies. Shared contracts naturally have high fan-in.
- Generated snapshots are evidence only. Regenerate after an approved move batch when comparing
  graphs, but do not turn changing inventories into a duplicate product roadmap.

## Read-only snapshot generator

```python
import ast
import collections
import csv
import io
import json
import posixpath
import re
import subprocess
import sys

revision = subprocess.check_output(
    ["git", "rev-parse", sys.argv[1] if len(sys.argv) > 1 else "HEAD"], text=True
).strip()
paths = (
    subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "-z", revision])
    .decode()
    .split("\0")[:-1]
)
contents = {p: subprocess.check_output(["git", "show", f"{revision}:{p}"]) for p in paths}
modules = {
    p[:-12].replace("/", ".") if p.endswith("/__init__.py") else p[:-3].replace("/", "."): p
    for p in paths
    if p.endswith(".py")
}
edges = set()
dynamic = []
for module, path in modules.items():
    tree = ast.parse(contents[path].decode())
    package = module if path.endswith("/__init__.py") else module.rpartition(".")[0]

    class Visitor(ast.NodeVisitor):
        scope = "module"

        def visit_FunctionDef(self, node):
            previous = self.scope
            self.scope = "deferred"
            self.generic_visit(node)
            self.scope = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_If(self, node):
            previous = self.scope
            if ast.unparse(node.test) in ("TYPE_CHECKING", "typing.TYPE_CHECKING"):
                self.scope = "typing"
            for child in node.body:
                self.visit(child)
            self.scope = previous
            for child in node.orelse:
                self.visit(child)

        def visit_Import(self, node):
            for alias in node.names:
                if alias.name in modules and alias.name != module:
                    edges.add((module, alias.name, self.scope, node.lineno))

        def visit_ImportFrom(self, node):
            if node.level:
                parts = package.split(".") if package else []
                base = ".".join(parts[: len(parts) - node.level + 1])
                if node.module:
                    base += ("." if base else "") + node.module
            else:
                base = node.module or ""
            for alias in node.names:
                candidate = f"{base}.{alias.name}" if base else alias.name
                target = candidate if candidate in modules else base
                if target in modules and target != module:
                    edges.add((module, target, self.scope, node.lineno))

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute) and node.func.attr in (
                "import_module",
                "iter_modules",
            ):
                dynamic.append((path, node.lineno, ast.unparse(node)))
            self.generic_visit(node)

    Visitor().visit(tree)


def graph_for(scopes=None, production=True):
    graph = {m: set() for m in modules if not production or not m.startswith("tests")}
    for source, target, scope, line in edges:
        if source in graph and target in graph and (scopes is None or scope in scopes):
            graph[source].add(target)
    return graph


def cycles(graph):
    index = 0
    indices, lows, stack, active, found = {}, {}, [], set(), []

    def visit(vertex):
        nonlocal index
        indices[vertex] = lows[vertex] = index
        index += 1
        stack.append(vertex)
        active.add(vertex)
        for target in sorted(graph[vertex]):
            if target not in indices:
                visit(target)
                lows[vertex] = min(lows[vertex], lows[target])
            elif target in active:
                lows[vertex] = min(lows[vertex], indices[target])
        if lows[vertex] == indices[vertex]:
            group = []
            while True:
                member = stack.pop()
                active.remove(member)
                group.append(member)
                if member == vertex:
                    break
            if len(group) > 1:
                found.append(sorted(group))

    for vertex in sorted(graph):
        if vertex not in indices:
            visit(vertex)
    return sorted(found)


groups = collections.defaultdict(lambda: [0, 0, 0])
rows = []
for path in sorted(paths):
    data = contents[path]
    top = path.split("/")[0] if "/" in path else "(root)"
    lines = len(data.splitlines()) if b"\0" not in data and not path.endswith(".pdf") else 0
    groups[top][0] += 1
    groups[top][1] += len(data)
    groups[top][2] += lines
    if path.startswith("public_rules/"):
        rights = "Public-source/generated mixed material; retain source provenance"
    elif path == "package-lock.json":
        rights = "Generated third-party dependency metadata; licenses remain distinct"
    elif b"SPDX-FileCopyrightText: 2026 Mindstep Corporation" in data[:1000]:
        rights = "Explicit Mindstep Corporation SPDX notice"
    elif path.endswith(".py") and path.startswith("infrastructure/migrations/"):
        rights = "Applied project migration; no notice added retrospectively"
    else:
        rights = "Project-maintained; consult LICENSING.md, no per-file attribution inferred"
    rows.append((path, len(data), lines, top, rights))

js_edges = []
template_refs = []
literal_js_refs = []
js_patterns = re.compile(
    r"""(?:\bimport\s+(?:[^;]+?\s+from\s*)?|\bexport\s+(?:\*|\{[^}]*\})\s+from\s*|\bimport\s*\()\s*['"]([^'"]+)['"]"""
)
for path in paths:
    if path.endswith((".mjs", ".js")):
        text = contents[path].decode()
        for match in js_patterns.finditer(text):
            specifier = match.group(1)
            if specifier.startswith("."):
                resolved = posixpath.normpath(
                    posixpath.join(posixpath.dirname(path), specifier.partition("?")[0])
                )
                if resolved in contents:
                    js_edges.append((path, resolved))
    if path.startswith("templates/"):
        for match in re.finditer(
            r"""filename=['"]([^'"]+\.(?:mjs|js|css))['"]""", contents[path].decode()
        ):
            template_refs.append((path, "static/" + match.group(1)))
    if path.startswith("tests/") and path.endswith((".mjs", ".py")):
        for match in re.finditer(
            r"""(?:\.\./)*static/([\w./-]+\.(?:mjs|js))""", contents[path].decode()
        ):
            literal_js_refs.append((path, "static/" + match.group(1)))

graph = graph_for()
incoming = collections.defaultdict(set)
for source, targets in graph.items():
    for target in targets:
        incoming[target].add(source)
ranking = sorted(
    (
        (
            module,
            len(incoming[module]),
            len(graph[module]),
            len(contents[modules[module]].splitlines()),
        )
        for module in graph
    ),
    key=lambda r: (-r[1], -r[2], r[0]),
)
output = io.StringIO()
writer = csv.writer(output, lineterminator="\n")
writer.writerow(["path", "bytes", "text_lines", "responsibility_directory", "rights_evidence"])
writer.writerows(rows)
inventory = output.getvalue()
edge_output = io.StringIO()
writer = csv.writer(edge_output, lineterminator="\n")
writer.writerow(["language", "source", "target", "scope", "line"])
writer.writerows(
    ("python", source, target, scope, line) for source, target, scope, line in sorted(edges)
)
writer.writerows(
    ("javascript", source, target, "literal", "") for source, target in sorted(set(js_edges))
)
writer.writerows(
    ("template", source, target, "static_url", "") for source, target in sorted(set(template_refs))
)

js_graph = {p: set() for p in paths if p.startswith("static/") and p.endswith((".mjs", ".js"))}
for source, target in js_edges:
    if source in js_graph and target in js_graph:
        js_graph[source].add(target)
summary = {
    "revision": revision,
    "files": len(paths),
    "bytes": sum(len(c) for c in contents.values()),
    "directories": dict(sorted(groups.items())),
    "python_modules": len(modules),
    "production_python_modules": len(graph),
    "python_edges_unique": len({(s, t) for s, t, _, _ in edges}),
    "production_python_edges": sum(map(len, graph.values())),
    "module_cycles": cycles(graph_for({"module"})),
    "conservative_cycles": cycles(graph),
    "js_cycles": cycles(js_graph),
    "coupling": ranking[:25],
    "dynamic_imports": dynamic,
    "large_source_files": sorted(
        (
            (p, len(contents[p].splitlines()), len(contents[p]))
            for p in paths
            if p.endswith((".py", ".mjs"))
        ),
        key=lambda r: -r[1],
    )[:20],
}
print(json.dumps({"summary": summary, "inventory": inventory, "edges": edge_output.getvalue()}))
```
