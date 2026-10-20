# ARCH-01A: Dependency-based repository organization plan

Issue: [#69](https://github.com/colleeseum/ForeView/issues/69), parent
[#68](https://github.com/colleeseum/ForeView/issues/68).

Status: accepted implementation plan as of 2026-10-20. Planning delivery landed in PR #74;
the maintainer accepted the remaining scope/sign-off in #69. Each implementation batch still
requires its own reviewed PR and explicit merge authorization. This document is not a claim
that all proposed moves have been implemented.
Baseline: `cba77584e68084ccbaf3ac068e59bed3bff4add7`, 2026-10-14. Uncommitted restart-script, Makefile and README work
is explicitly excluded from the measurements and this change.

## Recommendation

Organize browser implementation modules by their actual consumers, and application services by
capability. Keep the existing layers, filenames, public identifiers and provider packages.
Do not replace vanilla JavaScript, introduce a build system, consolidate small domain types,
rename financial concepts or merge unrelated provider interfaces.

The exact move map and batch boundaries are accepted for #70, #71 and #75, using compatibility
policy 2 below. Changes to that scope require separate agreement before implementation.
For #72, the current recommendation is a documented no-relocation/no-unified-registry outcome,
subject to its focused review. This is not an already-made architectural decision.

## Evidence and reproducibility

- [Tracked file inventory](arch-01a/tracked-files.csv): every baseline path, Git-blob byte size,
  text-line count, responsibility directory and copyright/provenance evidence.
- [Dependency edges](arch-01a/dependencies.csv): Python imports with scope/line, literal JavaScript
  imports, and Flask template static references. Symbols use Python module names; browser targets
  use repository paths.
- [Summary](arch-01a/summary.json): counts, coupling, discovery call sites, largest source files
  and strongly connected component results.
- [Read-only method and generator](arch-01a/method.md): fixed-revision reproduction and limitations.
- [Exact proposed move map](arch-01a/move-map.csv): 29 browser implementations, 27 service
  implementations and four synthetic tools, each with exact old/new paths and proposed PR batch.
  Files not listed stay put. The synthetic-tool batch was added after maintainer feedback;
  the baseline inventory and measured dependency graph remain unchanged.

This snapshot has 604 tracked files totaling 7,472,421 bytes, including public source artifacts.
There are 362 Python modules (300 outside tests), 813 distinct production Python import pairs
and 77 literal imports between production browser modules. The all-source Python graph has 1,112
distinct import pairs. These are import counts, not call frequency or performance measurements.

| Existing directory | Tracked files | Blob bytes | Text lines |
| --- | ---: | ---: | ---: |
| `(root)` | 24 | 179,188 | 4,567 |
| `.github` | 1 | 587 | 23 |
| `account_types` | 7 | 4,709 | 136 |
| `docs` | 8 | 75,312 | 1,264 |
| `domain` | 54 | 38,516 | 1,363 |
| `expense_sources` | 7 | 16,257 | 391 |
| `income_sources` | 4 | 5,948 | 137 |
| `infrastructure` | 24 | 62,803 | 1,470 |
| `ingestion` | 11 | 18,690 | 496 |
| `institution_support` | 11 | 13,392 | 369 |
| `institutions` | 41 | 151,771 | 3,763 |
| `localization` | 16 | 133,314 | 2,557 |
| `projection` | 48 | 110,031 | 2,908 |
| `public_pension_sources` | 4 | 3,847 | 87 |
| `public_rules` | 132 | 5,011,325 | 83,136 |
| `repositories` | 31 | 223,373 | 5,434 |
| `scripts` | 3 | 3,158 | 93 |
| `services` | 28 | 137,359 | 3,320 |
| `static` | 31 | 206,045 | 3,987 |
| `tax_notices` | 5 | 4,634 | 106 |
| `templates` | 14 | 85,709 | 947 |
| `tests` | 79 | 840,324 | 19,437 |
| `web` | 21 | 146,129 | 3,512 |

Text lines include blanks, comments and source HTML/data, not just executable code. Public-rule
artifacts account for most bytes; their size is not evidence of application-module disorder.
The inventory records evidence of rights, not a new legal ownership assertion. Government sources,
generated data and dependency metadata retain their applicable provenance and notices.
No CODEOWNERS file assigns people to components; directory responsibility is not human ownership.

## Dependency findings

No multi-module strongly connected components were found in either the module-only Python graph,
the conservative graph including deferred/typing imports, or the literal production JS graph.
Do not interpret this as proof that arbitrary runtime discovery or extension code cannot cycle.
Implicit package initialization, computed imports and callback invocation are outside this graph.

| Python module | Production fan-in | Fan-out | Text lines |
| --- | ---: | ---: | ---: |
| `domain.validation_error` | 42 | 0 | 11 |
| `domain.money` | 36 | 1 | 60 |
| `projection.public_rules` | 21 | 11 | 40 |
| `repositories.account_repository` | 21 | 6 | 496 |
| `ingestion.pdf_document` | 13 | 1 | 35 |
| `repositories.transaction_repository` | 12 | 6 | 556 |
| `repositories.balance_snapshot_repository` | 12 | 3 | 172 |
| `services.transaction_service` | 11 | 10 | 327 |
| `web.localization` | 11 | 4 | 67 |
| `repositories.import_batch_repository` | 11 | 1 | 136 |
| `web.dependencies` | 11 | 0 | 14 |
| `institution_support.registry` | 10 | 4 | 118 |

The highest fan-in belongs to shared money/validation contracts, public-rule models and central
repositories. This is largely expected reuse, not evidence that those modules should be split.
`services.transaction_service` is a real cross-capability coordinator: imports, account edits,
dashboard reads and Questrade sync use it. Its relocation needs wider integration coverage than
a pure parser, but the inventory does not justify changing its responsibilities.

High fan-out is similarly concentrated at composition/workflow boundaries:
`services.database_initialization` and `synthetic_runtime` have 24 targets each;
`web.income_routes` and `web.salary_projection_routes` have 20;
`app` and `web.transaction_routes` have 17. Keep those responsibilities intact during moves.

Concrete relationships to preserve:

- `services.dashboard_query` coordinates account/real-estate summaries and transactions, then
  calls `services.dashboard.build_dashboard_summary`. Keep that builder with dashboard/reporting,
  not in a miscellaneous utilities package.
- `services.income_tax_snapshot_service` calls `income_tax_source_resolver`, with correction
  validation sharing the same domain concept catalog. Group these three income services.
- CSV importing and statement row writing call reconciliation checkpoints; Questrade sync and
  institution importers call transaction services. Preserve that direction and transaction scope.
- `static/accounts.mjs` assembles dialogs, API/state and render modules. These belong together.
- `account-types.mjs` is used by accounts, dashboard, setup and transactions;
  `income-source-label.mjs` is used by income and salary projection. Both belong in shared
  presentation, not under the first feature that happened to introduce them.
- `button-action.mjs` currently has one production consumer, connections;
  `latest-request.mjs` has one, transactions; `ownership-fields.mjs` belongs to the accounts
  workspace. Keep them feature-local rather than treating every helper as shared.
- Help is a cross-page capability with its own entrypoint. It is not a generic formatting utility.

Normal small-module design should remain: `domain/` has 54 files but only 38,516 bytes;
typed public-rule files already have cohesive subpackages. One primary type per file is the
established convention. Counting files alone does not justify flattening types into large modules.

The largest files include `tests/test_app_routes.py` (2,786 lines),
`tests/test_localization.py` (1,026), `repositories/expense_repository.py` (800),
`web/income_routes.py` (585) and `web/salary_projection_routes.py` (556).
Splitting their logic/tests is a different refactor, not part of the proposed directory moves.

## Before/after organization

Current: 31 root files in `static/`, including 29 ES modules, one classic CSRF script and CSS.
Proposed: keep `static/csrf.js` and `static/style.css` at their existing URLs; group the 29 ES
module implementations under the following directories. Preserve filenames.

```text
static/
  shared/        account types, HTML, i18n, locale formatting, form state, income source labels
  accounts/      assets workspace state/API/rendering, account/GIC dialogs, real estate, ownership
  transactions/  page, row rendering, import messages, latest-request guard
  income/        factual income page and correction workflow
  expenses/      factual expense page/import workflow
  dashboard/     summary page
  connections/   connection page and button action helper
  projections/   salary projection page
  setup/         household setup page and value helpers
  help/          searchable/contextual help entrypoint
```

Current: 27 implementation files plus `services/__init__.py` in one directory.
Proposed: retain the root package and add minimal, non-eager-importing `__init__.py` files
under these capability directories. Avoid re-export barrels that load unrelated services.

| Proposed package | Implementations and responsibility |
| --- | --- |
| `services/accounts/` | aggregation, account/real-estate summaries, fixed-term deposit creation |
| `services/transactions/` | transaction coordination and reconciliation checkpoints |
| `services/imports/` | generic CSV import, account resolution, UFile/CRA/RQ/Retraite parsers |
| `services/income/` | snapshot, source resolution and factual correction validation |
| `services/expenses/` | expense read/calculation workflow and document import coordination |
| `services/reporting/` | dashboard builder/query and factual reporting query |
| `services/projections/` | salary workflow, scenario cloning and verified public-rule catalog |
| `services/runtime/` | initialization, backup, startup repairs and legacy deposit helper |

`services/projections/` coordinates use of `projection/`; it does not replace the existing
calculation/public-rule packages. The runtime legacy helper is not an applied numbered migration;
all files under `infrastructure/migrations/` remain immutable and unmoved.
Added package initializers increase file counts. This plan improves discoverability, not file-count
reduction, coupling reduction, or measured performance.

### Synthetic development tools: ARCH-01E (#75)

There is no demonstrated runtime requirement to keep the four synthetic generators at the
repository root. They are development/test tools, not production entrypoints. Their current
root paths are used by tests and documented commands; those references require coordinated updates.
They belong in a separate batch from #71's application services.

```text
devtools/
  __init__.py
  synthetic/
    __init__.py
    synthetic_documents.py
    synthetic_expenses.py
    synthetic_questrade.py
    synthetic_runtime.py
```

Retain existing filenames and exported APIs. Use minimal non-eager package initializers and
keep reusable functions/classes importable without executing CLI work. Existing guarded main
sections remain thin command-line entrypoints; do not combine relocation with a generator/CLI
redesign or create new generation behavior. Invoke loaders as modules from the repository root,
for example `python -m devtools.synthetic.synthetic_runtime .runtime/dev`.

Two measured resource dependencies need explicit repository-root resolution:

- `synthetic_runtime.py` currently uses `Path(__file__).parent / "public_rules"`.
- `synthetic_questrade.py` currently uses its parent for
  `tests/fixtures/questrade/sync_scenarios.json`.

After relocation, neither immediate parent is the repository root. Resolve these resources from
the known repository layout, not from the shell's working directory. Keep destination-path
semantics, `.runtime/dev`, private runtime paths and tracked fixture/public-rule locations unchanged.
Update synthetic-module imports, test/browser fixture imports and mocks, Makefile loader commands,
README examples, mypy's explicit file selection and Bandit's scan roots together. Verify coverage
still measures the moved files. Production code must not gain a dependency on `devtools/`.

Preserve runtime creation's no-overwrite guard, the loaders' synthetic-runtime refusal checks,
idempotency and generated financial meaning. Test imports without side effects, all loader CLIs,
resource lookup independent of cwd, rejection without writes and real-browser fixture creation.
Compare normalized facts and fixture content, not newly demanded byte determinism for existing
variable PDF IDs, timestamps or secrets. No generated private artifacts are committed.

Without compatibility launchers, these 20 tracked files would remain at the repository root:

```text
.gitattributes
.gitignore
.pre-commit-config.yaml
AGENTS.md
CONTRIBUTING.md
DISCLAIMER.md
LICENSE
LICENSING.md
Makefile
NOTICE
README.md
app.py
finance.config.example.json
package-lock.json
package.json
pyproject.toml
requirements-dev.txt
requirements.txt
runtime_backup.py
update_public_rules.py
```

Temporary root import aliases/CLI launchers may remain if required by the compatibility policy.
This is tooling relocation, not relocation of synthetic or private runtime data.

The CSV is the exact implementation move map. It does not authorize moving tests, templates,
catalogs, production/operational root CLIs, public data, repositories, domain types or route modules.

## Provider review: conditional no-change recommendation

The similar identity/version/help fields do not establish one interchangeable business interface.

| Family | Actual behavior that a relocation/unification must preserve |
| --- | --- |
| Institutions | name/alias normalization, sorted first-match discovery, CSV fallback, live connections, repairs and source tags |
| Account types | classification, liquidity and supported account capabilities; sorted discovery |
| Expenses | package discovery, required detector/parser, multiple-match rejection and preview/confirmation |
| Income | explicitly assembled UFile provider, optional detector, factual-income output and adjacent help file |
| Tax notices | explicitly assembled jurisdiction notice parsers and assessment output |
| Public pensions | explicitly assembled statement parsers and pension output |

The three discovery implementations use `importlib`/`pkgutil`, but differ in skipped modules,
validation, assembly timing and detection ordering. Expense discovery currently does not explicitly
sort modules. That observation is not permission to change its selection behavior in a move PR.
The three explicit document registries are small; moving them under a generic `providers/` name
would introduce import churn and discovery risks without removing a demonstrated runtime problem.

Localization already has a shared per-field resolver in `localization/provider_content.py` and
the HTTP adapter in `web/localization.py`. Reuse it; do not create another metadata/fallback layer.
Do not turn optional provider fields into a compulsory universal base class.
#72 should confirm this no-change recommendation or produce its own justified, approved map.

## Rewrite strategy and path-sensitive surfaces

Use `git mv` for each approved implementation, then update only imports and path configuration.
Do not combine moves with cleanup, algorithm changes, terminology changes or formatting churn.

| Surface | Required treatment in the implementing PR |
| --- | --- |
| JS module imports | resolve each old relative specifier to its old target; map both source and target, then derive the new relative path; preserve side effects and loading order |
| Template scripts | update literal `url_for('static', filename=...)` values in the exact template edges CSV; retain endpoint, module type and cache-version parameters |
| CSRF / CSS | keep existing root paths and security script ordering; no CSS URL references were found needing relocation |
| Browser tests | update literal and computed `../../static/` imports, including query-string cache busting; update `tests/js/localization-fixture.mjs` and HTML URL assertions |
| JS syntax / coverage | replace root-only traversal in Makefile and c8 `static/*.mjs` with recursive traversal/patterns before the first move |
| Python imports | rewrite exact module prefixes for mapped files, including package imports/re-exports, deferred imports and institution callers; no blind replacements in source labels or data |
| Python mocks | update patch targets to the namespace actually looked up by the caller; imported function aliases must still be patched at the use site |
| Python coverage | replace `services/*.py` with `services/**/*.py` in main and integration reports; update runtime-backup omit to its exact new path |
| Typing / security | mypy's `services` directory selection and Bandit's recursive roots already cover children; verify actual reports, do not lower thresholds |
| Localization reference audit | existing Python/JS catalog audits use recursive traversal; retain it and verify both old compatibility modules and new implementations if aliases are chosen |
| Root CLIs / resources | keep app, runtime backup and update-public-rules at root; move only the four synthetic tools under #75, updating module commands and repository-root resource lookup without moving runtime/data locations |
| Synthetic tooling checks | update explicit synthetic-file entries in mypy/Bandit to include `devtools`; retain browser/test imports, refusal guards, idempotency and actual coverage instrumentation |
| CI / hooks / license checks | CI currently checks identity, not full QA; hooks run Makefile coverage; license scan walks tracked files and must include new notices; preserve existing identities |
| Runtime / data | no migrations, schema changes, source-tag changes, provider keys/CalVer changes, locale preference moves or private runtime mutations |

Current coverage behavior was checked against installed tooling:
`coverage.files.GlobMatcher('services/*.py')` excludes
`services/transactions/transaction_service.py`; the recursive pattern includes it.
c8's installed test-exclude matcher similarly excludes `static/income/income.mjs` with
`static/*.mjs`, and includes it with `static/**/*.mjs`.
A moved-file coverage sentinel must prove moved implementations are instrumented; a passing
aggregate threshold by itself is insufficient.

Dynamic discovery is explicitly outside the static graph. Keep the existing provider package
names, discovery defaults, provider factories and connection-blueprint registration unchanged.
No CSP policy or JS bundler path assumptions were found in tracked configuration. This is an
observation of this revision, not a promise about deployment outside the repository.

## Compatibility policy

Module and asset paths are changing even though financial/UI behavior must not change.
Repository evidence does not establish whether external plugins import `services.*`, or whether
maintainers require already-open/cached pages to keep loading old static module URLs. Synthetic
tools also have root import and CLI paths whose compatibility must be considered explicitly.

On 2026-10-14 the maintainer approved policy 2 for #70/#71/#75: use canonical new internal
paths without compatibility aliases, update tracked consumers atomically in each batch, and
require a full browser reload on deployment. This does not change persisted data or public APIs.
The alternatives considered were:

1. Retain old paths temporarily with tested ES re-exports/entrypoint loaders and identity-preserving
   Python module aliases. Update tracked consumers to canonical new paths. Verify one module/state
   instance and old/new patch behavior. Preserve old synthetic CLI invocations with tested thin
   launchers if needed. Extra compatibility files remain in flat roots; removal
   requires separate approval and must not be hidden in a later batch.
2. Explicitly approve changing these internal paths without compatibility aliases. All tracked
   consumers must be rewritten atomically per batch, and deployment must require a full browser
   reload. Do not claim undocumented external import compatibility.

Policy 1 was the conservative proposal before maintainer agreement. Policy 2 is now selected;
do not add compatibility files in these move batches. The pinned evidence snapshots remain a
record of the pre-move revision, not the current filesystem layout.

## Incremental PR boundaries

Each row is a separate reviewed PR on a fresh branch based on accepted main; do not stack all
moves before validating earlier batches. Preserve all four existing coverage thresholds and run
`make qa` in every implementation PR.

ARCH-01B (#70) and ARCH-01C (#71) are coordination parents. Their PR-sized implementation
batches are tracked as nested issues: 70-1 through 70-4 in #76 through #79, and 71-1 through
71-3 in #80 through #82. Use each leaf issue for its branch, commit and completing PR; reference
the parent without closing it prematurely. The leaf issue requirements are self-contained in
GitHub. Add every leaf issue to the authoritative Project and verify membership.

| Batch | Boundary | Prerequisites / focused evidence |
| --- | --- | --- |
| 69 | inventory, graph, exact map, risks and approval questions only | completed in PR #74; plan accepted; no code moves in that planning PR |
| 70-1 | six shared ES modules; recursive JS tooling and consumers | catalog/key audit, locale formatter, account-type and module-state tests |
| 70-2 | accounts (9), dashboard (1), setup (2) | assets/GIC/ownership tests, unchanged API requests and factual state |
| 70-3 | transactions (4), connections (2) | reconciliation/import prompt/error tests, preserved async request guards and connection actions |
| 70-4 | income (2), salary projection (1), expenses (1), help (1) | bilingual PDF/CSV workflows, correction lifecycle, help search/focus and RTL acceptance |
| 71-1 | accounts (4), reporting (3), projections (3); recursive service coverage | account aggregation, public-rule approval, salary and dashboard invariance |
| 71-2 | income (3), imports (6), expenses (2) | precedence/fingerprints, parser/source detection, import hashes and rollback |
| 71-3 | transactions (2), runtime (4) | all institution/Questrade paths, reconciliation/balances, migrations/backup and fresh app startup |
| 75-1 | four synthetic tools under `devtools/synthetic/`; CLI, imports and tooling updates | after #69 scope agreement; coordinate with landed #71 imports; preserve generated facts, refusal/overwrite guards, idempotency, resource lookup and browser fixture setup |
| 72 | provider decision record first; no relocation recommended | approve any counterproposal separately before implementation |

The accepted policy does not retain compatibility aliases. If that requirement changes, record
and approve a revised policy before the affected batch; do not silently introduce duplicate paths.

## Risks and acceptance checks

- Browser 404s, wrong relative imports and duplicate initialized state: request every old/new
  supported asset URL, run real Chromium en-CA/fr-CA workflows, and verify no console exceptions.
- Silent coverage loss: inspect coverage JSON/XML for moved paths and a known branch/function,
  not merely test counts. Keep at least the current coverage floors.
- Mock drift: use-site patch tests must still intercept the dependency. Successful imports alone
  do not prove patch identity or preserved monkeypatch semantics.
- Discovery/initialization cycles: run app import/factory and provider discovery in a fresh process,
  not only a warmed pytest session. Compare provider keys, versions, importer ordering and routes.
- Data drift: migrations must be byte-identical; normalized money, dates, raw source tags,
  document hashes, correction fingerprints and package approvals must be unchanged.
- Resource roots: keep app, backup, public-rule updater and provider-adjacent help files in place;
  #75 must explicitly fix relocated synthetic-tool resource lookup without changing destinations.
- Financial behavior: compare equivalent synthetic API payloads and computed rows, ignoring only
  implementation-only asset/module path differences explicitly approved above.
- Stale guidance: update architecture, agent instructions, contributor setup, institution guidance,
  runtime examples and tooling wherever the specific batch makes them inaccurate. Do not describe
  a proposed layout as already implemented.

## Rollback

Each move PR must contain only coherent moves, necessary rewrites, tests and shared-context edits.
Before landing, record its accepted parent commit and an asset/import smoke baseline.
No database rollback is needed because schema and authoritative facts must not change.

If regression is found after landing, revert that PR's squash commit with `git revert <commit>`
on a new reviewed fix branch; rerun `make qa` and smoke checks before landing the revert.
Do not reset shared main or rewrite unrelated commits. Revert later dependent move batches first,
in reverse order, when their imports depend on the batch being rolled back.
Restore the matching old assets/templates together and restart using the existing operational
procedure; keep runtime paths and private data untouched. Restore the matching pre-move paths
as part of the revert rather than adding compatibility aliases under the selected policy.

## Accepted scope and remaining review boundaries

- The target paths and batch boundaries in `move-map.csv`, including the four synthetic tools
  under #75, are accepted. Evidence snapshots remain pinned to the original baseline.
- Compatibility policy 2 is selected: canonical internal paths, atomic tracked-consumer updates,
  no legacy import/CLI aliases and a full browser reload after deployment.
- No provider relocation or universal registry is approved. The no-change recommendation is the
  starting position for #72's separate evidence-based review; that issue can conclude no change
  or propose a separately approved implementation.
- ARCH-01A is complete. Remaining implementation and provider-review issues stay open; completion
  of the plan does not authorize merging their PRs without review and maintainer approval.
