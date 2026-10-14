# ARCH-01A — Repository structure inventory and proposed refactoring

Status: **Draft for maintainer review; evidence collection pending.** Parent #68, issue #69.
This document proposes *how to decide* on file moves; it does not authorize them.

## Existing boundaries (confirmed from tracked architecture and representative modules)

- `app.py` is the Flask composition root.
- `domain/` owns financial facts; `repositories/` owns SQLite persistence;
  `services/` owns workflows and read models; `web/` owns HTTP.
- `institutions/<provider>/` keeps institution-specific parsers and connection adapters together.
- `static/` holds browser ES modules; `templates/` renders HTML;
  `localization/` holds locale catalogs and contracts.
- `projection/`, `public_rules/`, and `infrastructure/migrations/` have
  distinct responsibilities and should not be flattened or casually renamed.

These are architectural observations, **not** evidence that every package needs moving.

## Reproducible inventory

From a complete local checkout of the target commit:

```sh
python scripts/architecture_inventory.py
python scripts/architecture_inventory.py --json > /tmp/foreview-architecture.json
```

The tool reads only Git-tracked paths, not private runtimes. It reports top-level
file counts and bytes, Python AST import edges and strongly connected components,
high-incoming-dependency modules, relative JS import specifiers, and literal HTML
asset references. It uses only the standard library. It **does not** execute
application code or modify files.

**Limits:** Static analysis cannot reliably resolve dynamic provider registration,
imports inside computed strings, conditional imports, Jinja `url_for` calls,
JS template strings, Python `__getattr__` exports, or external tooling.
Unresolved imports include stdlib and third-party packages; do not treat every
unresolved import as an error. Validate actual consumers with `rg`, browser
tests, and runtime smoke tests. Review the analyzer itself before relying on its
cycle and import results.

## Candidate moves — not yet approved

| Current location | Candidate target | Decision criteria |
| --- | --- | --- |
| `static/accounts*.mjs`, `static/account-*.mjs` | `static/js/accounts/` | Keep entrypoint and shared helpers distinguishable; enumerate every import/template reference. |
| `static/transactions*.mjs`, transaction helpers | `static/js/transactions/` | Include reconciliation and import UI only if cohesive. |
| `static/income*.mjs`, `static/expenses*.mjs` | `static/js/income/`, `static/js/expenses/` | Verify shared dependency ownership. |
| `static/i18n.mjs`, `static/locale-format.mjs`, reusable DOM helpers | `static/js/core/` | Prevent feature modules importing from other feature internals. |
| `services/expense_*.py` | `services/expenses/` | Ensure tests and import services have compatible dependencies. |
| `services/dashboard_query.py`, `services/reporting_query.py` | `services/reporting/` | Review consumers and read-model dependencies. |
| `services/*import*.py`, `services/*reconciliation*.py` | `services/imports/`, `services/transactions/` | Group by responsibility, not substring alone. |
| Provider-related root packages | **No move by default** | Move only after ARCH-01D proves reduced coupling/duplication. |
| `domain/`, `repositories/`, `web/` | **Keep for now** | Reconsider only if measured navigation/coupling problems justify it. |

This is a **candidate mapping**, not a complete file-by-file old/new path
inventory. ARCH-01B and ARCH-01C must not begin until the final map is reviewed.

## Risk and validation checklist

1. Inventory `git ls-files`, module import graph, high-coupling modules and
   strongly connected components. Confirm actual package counts and outliers.
2. Search all Python import sites, including `unittest.mock.patch` strings,
   CLI scripts, mypy/coverage config, plugin registries, and provider discovery.
3. Search all JS imports (static/dynamic), HTML `url_for('static', filename=...)`,
   template includes, CSS URLs, browser test imports, and CSP assumptions.
4. Document each **exact** source -> destination path, affected references, and
   the minimal test(s) proving compatibility; classify as move, keep, or split.
5. Record before/after import cycles, layer violations, and module fan-in/fan-out.
   Avoid introducing compatibility shims unless required for external consumers.
6. Run `make qa` and exercise all page entrypoints, en-CA/fr-CA locale switching,
   provider discovery, imports, and financial reconciliation with synthetic data.
7. Confirm API contracts, source evidence, authoritative integer cents, migrations,
   tax rules, and private runtime paths are unchanged.
8. Use separate PRs for frontend and services. Keep each PR reviewable and
   behavior-preserving. Roll back by reverting that PR; no data migration expected.

## Decisions required before implementation

- Confirm the inventory at the intended base SHA and attach the summarized results.
- Approve an **exact** move map for ARCH-01B and ARCH-01C.
- Decide whether preserving original browser entrypoint paths as thin adapters
  is necessary for bookmarked/static integrations.
- Defer provider namespace changes to ARCH-01D; do not conflate registries.

## Completion definition for ARCH-01A

A maintainer-approved inventory report with actual counts, dependencies, cycles,
high-coupling hotspots, and an exact old/new file map, plus documented test
and rollback plan. **No production module moves in this issue.**
