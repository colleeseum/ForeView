# Architecture

This document describes the architecture currently implemented in the repository. It is not a
target-state design.

The accepted repository organization plan is recorded separately in
[`structure/arch-01a-plan.md`](structure/arch-01a-plan.md). Its scope is agreed, but implementation
PRs still require review and maintainer merge approval. Shared browser modules live under
`static/shared/`, and all browser feature implementations use capability directories.
All application service implementations use capability packages. Synthetic development tools
live under `devtools/synthetic/`, outside the production dependency graph.

## System shape

ForeView is a local-first personal and household financial management, analysis, and modelling
system backed by one SQLite database per runtime. Its implemented financial domains are currently
oriented toward Canadian personal finance, tax, and retirement planning. Server-rendered pages
establish the workspace, and vanilla JavaScript ES modules call JSON APIs for interactive behavior.
The application is assembled by `create_app(RuntimeConfig)` in `app.py`.

```text
Browser templates and ES modules
              |
         Flask blueprints
              |
   application services and read models
              |
       repository interfaces
              |
       per-runtime SQLite database

External documents and APIs
              |
 provider registries and ingestion adapters
              |
 services, repositories, and normalized domain records
```

The application is currently a single process and a single-user local workspace. It has CSRF
protection for state-changing browser requests but no user authentication or tenant isolation.

## Composition and runtime boundary

`app.py` is the composition root. It creates the Flask application, registers core and
institution-owned blueprints, installs CSRF verification, and exposes runtime dependencies through
`app.extensions`. Request handlers obtain the current database connection and other runtime
services through `web.dependencies.dependency`.

`infrastructure.runtime_config.RuntimeConfig` owns a runtime directory, immutable configuration,
SQLite connection creation, and optional TLS paths. The normal profiles are:

- `.runtime/dev` for disposable synthetic development data;
- `~/.local/share/retirement-finance/prod` for private data.

Runtime databases, configuration, credentials, and imported financial documents are deliberately
outside source control. The application binds to localhost by default.

## Main layers

### Domain

`domain/` contains mostly frozen dataclasses representing financial facts and projection values.
It has no persistence or HTTP responsibility. Monetary conversion helpers centralize cents and
`Decimal` handling. Public-rule packages reference the typed models under `projection/public_rules`.

### Persistence and migrations

`repositories/` contains all application SQL and converts SQLite rows into domain objects or
purpose-specific read rows. Services and routes depend on repositories rather than embedding SQL.

`infrastructure/domain_schema.py` contains the baseline schema retained for compatibility.
Numbered migrations under `infrastructure/migrations/` evolve existing runtimes. The migration
runner records applied versions in `schema_migrations`, validates recorded names, and commits each
migration separately. Startup also performs explicit data repairs and balance recalculation through
`services.runtime.database_initialization`.

Authoritative monetary facts use integer-cent columns and are converted to `Decimal`. Some legacy
`REAL` columns remain for compatibility and direct inspection.

### Application services and read models

`services/` coordinates workflows and builds read models. Examples include transaction balance
recalculation, reconciliation checkpoints, dashboard aggregation, runtime backup and restore,
public-rule catalog verification, salary projection, document parsing, and scenario cloning.

`services/accounts/` groups account aggregation, account and real-estate summaries, and fixed-term
deposit creation. `services/reporting/` owns the dashboard builder and dashboard/reporting queries.
`services/projections/` owns public-rule package verification, salary projection and scenario
cloning. `services/income/` owns source resolution, consolidated snapshots and correction validation;
`services/imports/` owns CSV ingestion, document account resolution, and tax/pension parsers;
`services/expenses/` owns factual expense workflows and statement-import coordination.
`services/transactions/` owns transaction coordination, balance calculation and reconciliation;
`services/runtime/` owns database initialization, legacy repairs and verified backup/restore.
Package initializers do not eagerly import implementations. Only `__init__.py` remains at the
service package root. Callers use canonical imports without
legacy aliases; these directory moves do not change HTTP or persistence contracts.

Read-oriented services such as `DashboardQuery`, `AccountSummaryQuery`, and
`RealEstateSummaryQuery` assemble presentation data without moving SQL out of repositories.

### Web and browser presentation

`web/` contains Flask blueprints and HTTP serialization. The shared `model` blueprint is assembled
from focused account, people, real-estate, reporting, and transaction route modules. Separate
blueprints own pages, dashboards, income records, public rules, help, institutions, and employment
projection.

`templates/` contains server-rendered HTML. `static/` contains framework-free browser modules,
with reusable modules for API calls, rendering, form state, dialogs, ownership, and help. Browser
tests use Node's test runner and jsdom. Shared localization, value formatting, HTML, form state,
account-type labels and income-source labels live under `static/shared/`. The accounts workspace
uses `static/accounts/`, the dashboard uses `static/dashboard/`, and household setup uses
`static/setup/`. Transactions and reconciliation UI modules use `static/transactions/`;
connection controls and their button-action helper use `static/connections/`. Income and corrections
use `static/income/`; expenses use `static/expenses/`; salary projection uses `static/projections/`;
and the shared help drawer uses `static/help/`. Only the classic CSRF script and stylesheet remain
at the static root. There are no legacy ES-module URL aliases.
Syntax and coverage checks traverse browser modules recursively and verify executed coverage
for every module.

The opt-in Sage foundation lives in `static/shared/ui.css`, loaded after the legacy stylesheet
by adopting surfaces. Its `fv-ui` scope and `fv-` components do not restyle unmigrated pages.
`static/shared/dialog.mjs` wraps native modal dialogs for explicit invoker/fallback focus return;
existing legacy dialogs are not automatically migrated. Component usage and the disposable
synthetic reference are documented in `docs/design/ui-foundation.md`.

The shared help API combines core articles and provider contributions under stable category IDs.
The help drawer renders expandable category ancestry, preserves category paths in search, and
expands the branch selected by page-level or contextual help. Provider hierarchy metadata is
adapted in the help route; browser rendering does not contain institution-specific branches.
When no valid contextual article is supplied, selection follows the first article in the rendered
category hierarchy, not the lowest article order across unrelated categories.

`localization/` provides a registry-backed presentation service with JSON message catalogs,
deterministic locale fallback chains, and a per-runtime language preference. Flask exposes the
selected locale, text direction, supported locales, translation function, and every browser
catalog required by the selected locale's fallback chain to templates. Framework-free browser
modules use the shared `static/shared/i18n.mjs` contract for lookup, interpolation, deterministic
fallback, and visible missing-key markers. The browser catalogs cover the primary dynamic
workflows; core help navigation, tooltips, and guidance use locale catalogs with per-field
fallback and resolved-language metadata. Provider help uses optional per-provider locale
dictionaries through the same resolver. Import guidance, display labels and About income,
tax-notice, public-pension and expense module names reuse that presentation adapter without
replacing original provider identity or provenance. About institution module names still render
the provider's original display name directly, without resolving its translations.
Owned validation exceptions carry stable codes and interpolation values to HTTP adapters, which
resolve localized messages and language metadata. Non-HTTP callers retain original diagnostic text.
Financial browser displays use shared Intl-based value helpers. Server-rendered expenses and
public tax rules use the Decimal-based `localization/value_formatter.py` adapter and offline
Babel CLDR locale data exposed through the Flask template context. These presentation adapters
do not change domain calculations, persisted values, input syntax, or raw source evidence.

The pytest acceptance suite runs headless Chromium against an isolated temporary synthetic runtime
to exercise localized interactions and RTL layout/focus. Playwright is development-only; the
production browser code remains framework-free. See `docs/localization.md` for the acceptance
scope and contributor installation instructions.

### Institution and ingestion adapters

`institution_support/` defines institution identity, document importer, CSV parser, help,
connection, and repair contracts. `institutions/` contains self-contained provider packages. The
registry discovers modules in name order and validates names, importer identity, and CalVer
versions. An institution can own document detection, parsing, import services, help, transaction
repair, and optional live connection routes.

`ingestion/` provides institution-neutral PDF and CSV handling, raw source retention, transaction
matching, deduplication, row writing, and reconciled-period guards. Institution parsers normalize
input; institution import services persist through repositories.

The detailed provider contract and extension procedure are maintained in
`institutions/README.md`.

### Other extension registries

- `account_types/` discovers account-type metadata providers such as non-registered, TFSA, RRSP,
  and RESP.
- `income_sources/` registers tax-return import sources. UFile is currently the implemented source.
- `tax_notices/` registers CRA and Revenu Québec notice parsers.
- `public_pension_sources/` registers public-pension statement parsers. A Retraite Québec
  participation statement is currently supported.
- `expense_sources/` discovers household expense-statement providers. Hydro-Québec electricity
  bills are currently supported.
- `projection/rule_update/` uses an explicit provider registry for official public-rule retrieval.

The institution, account-type, and expense-source registries use package discovery. Income,
tax-notice, public-pension, and public-rule providers are currently assembled explicitly in their
registries.

The [ARCH-01D provider review](structure/arch-01d-provider-review.md) documents why institution,
account-type, expense-source, income-source, tax-notice and public-pension packages and contracts
remain separate, the shared mechanisms already in use, and the observed policy differences.
Public-rule providers are outside that review's scope. It makes no provider relocation or
runtime change.

## Public financial rules

`projection/public_rules/` defines typed Pydantic models for annual jurisdiction rule sets,
brackets, parameters, source provenance, rounding, indexing, and projected-rule assumptions.
`projection/rule_update/` retrieves official source artifacts and writes deterministic packages to
`public_rules/<year>/<jurisdiction>/`.

Each package includes original source artifacts, hashes, a manifest, and canonical normalized JSON.
`PublicRuleCatalog` verifies paths, source hashes, manifest identity, and rule-set hashes when
loading. A normalized package is usable by calculations only after its exact content hash has been
approved in the runtime database.

## Factual records and projections

Factual assets, transactions, balances, ownership, annual income, assessments, registered-plan
room, and pension statements are stored independently of scenario assumptions.

Factual expenses are stored as dated evidence under user-defined required or discretionary
categories. Each record snapshots its category name and classification, may identify a person,
account, or real-estate association, and keeps import-batch and parser provenance when created by a
source module. The generic import service detects a provider for preview and re-detects and parses
the uploaded bytes during confirmation; extracted amount and period evidence are not accepted from
the browser. Stable expense identities distinguish separate streams such as Hydro and Energir
within the same Utilities category. Potential overlaps within one identity block the
annual factual total until every candidate has an explicit include or exclude decision. Repeated
source hashes enter the same review workflow even when editable identity fields differ. Recorded
totals remain factual; recurring statement periods can also produce a separately labelled
seasonal estimate from current actuals and an explicitly inflation-adjusted, complete
preceding-year baseline. Import providers must classify the amount basis explicitly. Scenario-level
household expense plans remain separate projection assumptions.

The consolidated income and tax read model resolves each same-year concept through assessment,
filed-return, and supported annual-record precedence. Factual corrections are separate append-only
revision streams above that resolver. Their stored source snapshots preserve audit history, while
review status is derived by comparing the stored fingerprint with the currently resolved source.
A domain-level concept catalog supplies the supported keys, labels, and annual-record mappings to
source resolution, correction validation, API output, and the snapshot presented by the browser.
The Income page can select a retained tax year and manages the append-only correction lifecycle,
including source-change review and revision-history presentation.

The implemented projection slice is employment and disposable income. `SalaryProjectionService`
combines a factual annual employment record or baseline, scenario settings, annual overrides,
approved public rules, salary growth, retirement-date proration, payroll contributions, and tax
calculation. Projected rows retain the public rule year and whether an older approved rule was held
constant.

The broader retirement schedule described in `docs/retirement-projection-concepts.md` is not yet
implemented. There is not yet a general registry that composes multiple projection algorithms over
different periods.

## Import integrity and reconciliation

Imports retain batches, hashes, and raw rows before producing normalized transactions. Matching
uses source content and occurrence counts so overlapping or repeated downloads do not silently
duplicate transactions. Known balances and statement reconciliations anchor calculated running
balances. Importing into a reconciled period is guarded and can mark the checkpoint for review.

Questrade is the only live account connection. It supports multiple named authorizations,
encrypted tokens, incremental activity synchronization, overlap lookback, and explicit historical
re-fetch.
Status reads use saved authorization metadata only and never refresh tokens. Synchronization
refreshes only its selected login, so another login's refresh failure cannot block it. Expected
refresh failures carry safe error codes to localized HTTP adapters; saved credentials survive
failed refreshes. The Connections UI isolates unavailable providers and retains explicit sync
and reconnect controls for saved authorizations.
Bulk synchronization skips unavailable providers and reports each outcome independently, retaining
successful summaries even if another synchronization or the subsequent status reload fails.
During a synchronization, a failed unauthorized-response refresh is retained for that login:
remaining components do not retry remote calls, and component errors retain their safe refresh
code for localized API guidance and subsequent status reads.

## Test and quality architecture

Python unit and integration tests live under `tests/`. Browser behavior tests live under
`tests/js/`. Development-only generators under `devtools/synthetic/` exercise imports without
committing private documents. Their package initializers are non-eager; production modules do not
import them. Resource lookup is repository-relative, while runtime destinations retain caller-relative
path semantics. See `README.md` for repository-root module commands.
The project enforces branch-aware Python and JavaScript coverage floors of at least 80
percent, plus Ruff, mypy, Bandit, dependency audits, and dedicated integration-coverage targets.
The exact commands are maintained in `Makefile` and summarized in `README.md`.
Service coverage filters include nested packages. The service coverage sentinel reads the main
and integration XML reports and requires executed function bodies and, where present, branches
in each capability-grouped implementation. Fresh-process tests check non-eager package imports,
canonical dependency identity, use-site patches and application startup in both import orders.
Document-provider tests also verify that registry-bound parser instances and detection functions
use the canonical implementations and that dependency patches reach those retained parser bindings.
The integration run includes backup/restore tests, including the root CLI round trip. Its existing
backup-specific aggregate coverage exclusion names the canonical runtime service path; the
executed-coverage sentinel still verifies every grouped service in both reports.
The synthetic-tool coverage sentinel uses the same executed-function/branch checks for all four
relocated generators in both reports. CLI and fresh-process tests cover unrelated working
directories, import side effects, no-overwrite/private-runtime guards and repeatable seeding.
