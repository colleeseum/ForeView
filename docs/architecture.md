# Architecture

This document describes the architecture currently implemented in the repository. It is not a
target-state design.

## System shape

Retirement Finance is a local-first Flask application backed by one SQLite database per runtime.
Server-rendered pages establish the workspace, and vanilla JavaScript ES modules call JSON APIs for
interactive behavior. The application is assembled by `create_app(RuntimeConfig)` in `app.py`.

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
`services.database_initialization`.

Authoritative monetary facts use integer-cent columns and are converted to `Decimal`. Some legacy
`REAL` columns remain for compatibility and direct inspection.

### Application services and read models

`services/` coordinates workflows and builds read models. Examples include transaction balance
recalculation, reconciliation checkpoints, dashboard aggregation, runtime backup and restore,
public-rule catalog verification, salary projection, document parsing, and scenario cloning.

Read-oriented services such as `DashboardQuery`, `AccountSummaryQuery`, and
`RealEstateSummaryQuery` assemble presentation data without moving SQL out of repositories.

### Web and browser presentation

`web/` contains Flask blueprints and HTTP serialization. The shared `model` blueprint is assembled
from focused account, people, real-estate, reporting, and transaction route modules. Separate
blueprints own pages, dashboards, income records, public rules, help, institutions, and employment
projection.

`templates/` contains server-rendered HTML. `static/*.mjs` contains framework-free browser modules,
with reusable modules for API calls, rendering, form state, dialogs, ownership, and help. Browser
tests use Node's test runner and jsdom.

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
- `projection/rule_update/` uses an explicit provider registry for official public-rule retrieval.

The institution and account-type registries use package discovery. Income, tax-notice,
public-pension, and public-rule providers are currently assembled explicitly in their registries.

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

The consolidated income and tax read model resolves each same-year concept through assessment,
filed-return, and supported annual-record precedence. Factual corrections are separate append-only
revision streams above that resolver. Their stored source snapshots preserve audit history, while
review status is derived by comparing the stored fingerprint with the currently resolved source.

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

## Test and quality architecture

Python unit and integration tests live under `tests/`. Browser behavior tests live under
`tests/js/`. Synthetic runtime and document generators exercise imports without committing private
documents. The project enforces branch-aware Python and JavaScript coverage floors of at least 80
percent, plus Ruff, mypy, Bandit, dependency audits, and dedicated integration-coverage targets.
The exact commands are maintained in `Makefile` and summarized in `README.md`.
