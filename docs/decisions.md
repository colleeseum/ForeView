# Durable design decisions

This document records decisions supported by the current implementation and tracked project
documentation. It does not reconstruct unavailable conversation history. When rationale cannot be
reliably inferred, the entry says so.

## Local-first, runtime-isolated storage

The application stores private data in a configurable runtime directory with one SQLite database
and one optional JSON configuration file. Synthetic development and private production runtimes
are separate. Source code, public rules, and synthetic fixtures may be committed; private runtime
data and credentials may not.

Reason: financial records and connection tokens are sensitive, while isolated synthetic data is
needed for repeatable development and testing.

## Application factory and explicit runtime dependencies

Flask applications are created through `create_app(RuntimeConfig)`. Runtime database access and
connection providers are supplied through application extensions and resolved per request. Runtime
state is not held in module-level database globals.

Reason: this permits isolated dev, prod, and test applications and prevents one runtime from
silently contaminating another.

## Explicit boundaries with SQL confined to persistence

Domain values, repositories, services, HTTP routes, and adapter modules have separate
responsibilities. Application SQL belongs in repositories or schema and migration infrastructure.
Institution modules persist through repositories.

The current persistence implementation uses Python's `sqlite3` directly rather than an ORM. The
repository does not establish that an ORM can never be adopted; any future change must preserve the
existing boundaries and justify its migration and complexity costs.

## Append-only database evolution

Applied numbered migration files are immutable. A schema or data change is introduced by adding a
new migration, not by editing an already applied migration. The migration ledger validates both
version and name.

Reason: private runtimes may have been upgraded at different times and must converge predictably.

## Integer cents and decimal financial arithmetic

Authoritative monetary persistence uses integer cents, and calculations use `Decimal` with
explicit rounding where required. Legacy `REAL` columns remain only for backward compatibility.
New code must not add authoritative binary floating-point money paths.

Reason: cent-exact storage and decimal arithmetic avoid cumulative binary rounding drift and make
financial results reproducible.

## Factual records are separate from assumptions and projections

Imported or entered assets, balances, transactions, annual tax facts, and public-pension records
are factual history. Scenario settings, annual overrides, future public-rule assumptions, and
projected rows are separate records. An override changes a scenario, not the factual source.

Reason: historical data must remain auditable and reusable across scenarios, while projections
must identify the assumptions that caused a result.

## Imports retain provenance and are idempotent

Document imports retain source batches, hashes, and raw rows. Normalized transaction matching uses
content and occurrence counts, and statement balances or reconciliation checkpoints anchor running
balances. Re-importing overlapping source data should not duplicate existing facts.

Reason: financial exports overlap, are downloaded repeatedly, and can contain genuinely identical
rows. A simple unique tuple or filename check is insufficient.

## Extension behavior belongs to provider contracts

Institution-specific parsing, importing, help, repairs, and live connections live in the
institution's own module and are discovered through a provider contract. Account types also use
discoverable providers. Tax-return, assessment, and pension-document sources use typed provider
contracts, although those registries are currently assembled explicitly.

Reason: supporting a new provider should not require spreading provider-specific branches across
the application core.

Provider module versions use CalVer. The code does not provide evidence for the historical reason
beyond the need to expose when parsing behavior last changed.

## Public rules are version-controlled data requiring explicit approval

Official source artifacts, normalized annual rules, manifests, provenance, and content hashes are
committed under `public_rules/`. Downloading or parsing a package does not approve it. The exact
normalized hash must be approved in each runtime before calculations use it.

Review covers structural rule changes as well as numeric changes. Independent sites can be used as
cross-checks, but official government publications remain authoritative.

Reason: calculations must remain reproducible after source websites change, and a successful
parser cannot determine whether a government introduced a new concept that needs code changes.

## Account aggregation preserves source semantics

Registered and non-registered assets are not made comparable by applying an arbitrary tax haircut.
Parent account balances explicitly state whether they include child GIC balances. Liquidity,
security holdings, ownership, maturity terms, and registered-account restrictions remain distinct
facts.

Reason: flattening these differences would double-count balances or present misleading available
cash and after-tax value.

## Projection results must remain explainable

Salary projection rows identify rule year and whether a rule was held constant. Annual overrides
are explicit and resettable. Future retirement projections are expected to retain provenance to
source accounts, events, assumptions, and public rules. A success probability or optimization
recommendation is not accepted without a defined method and assumptions.

Reason: a financial result that cannot be traced or reproduced is not suitable for planning or
comparison.

## Income snapshots preserve source precedence and provenance

For a given tax year and concept, assessment values take priority over filed-return values. When
neither source provides a supported concept, the annual factual record may supply that value. The
resolved value retains its source, document kind, jurisdiction, and line code when available. The
snapshot does not borrow a value from an older year to fill a newer year.

The annual factual record may itself have been entered manually or populated from a filed return;
it is not inherently a manual correction. Explicit corrections are append-only revisions that do
not modify underlying facts. Editing preserves the reviewed source fingerprint, confirmation
captures the currently resolved source, and review status is derived rather than stored mutably.
Supported correction concepts have one domain-level catalog used by resolution and validation.
Initial correction values are non-negative money amounts, including zero, and must include a
non-empty reason. Removing a correction restores normal source precedence without closing its
revision stream; a later correction appends a new create revision guarded by the tombstone's
revision number.

Reason: the consolidated view should prefer assessed facts while remaining traceable and should
not silently present stale values as current-year facts. Derived review status prevents a reimport
from silently validating or invalidating a user's correction.

## Security scope is local, not multi-tenant

The current application has CSRF protection, optional TLS, encrypted Questrade tokens, localhost
binding by default, backup integrity checks, and dependency/security scanning. It does not have
authentication, authorization, or tenant isolation and therefore must not be exposed to an
untrusted network.

No durable decision about a future hosted or zero-knowledge architecture can be inferred from the
repository.

## Synthetic data is the test boundary for private formats

Tests and development runtimes use generated people, accounts, statements, PDFs, and Questrade API
responses. Real financial documents and extracted personal details are not test fixtures and are
not committed.

Reason: parser and integration behavior must be reproducible without leaking private information.

## Public use is noncommercial and commercial licensing is separate

First-party software is source-available under the unmodified PolyForm Noncommercial License
1.0.0, with Mindstep Corporation as copyright holder. Commercial use requires a separate written
license. The public license also permits the noncommercial organizational uses it explicitly
identifies.

Concise SPDX notices identify first-party source files where their formats safely support comments.
Downloaded government sources, third-party material, generated files, binaries, lockfiles, and
other unsuitable formats are not relabeled. Existing applied migrations are not changed solely to
add notices because migrations are append-only.

Reason: individuals and qualifying noncommercial organizations may inspect, use, modify, and fork
the application without granting commercial exploitation rights. Standardized PolyForm terms are
used unchanged so the project does not create a custom software license.

## Project commit identity is explicitly enforced

Commits attributed to Serge Colle use `serge.colle@mindstep.ca` as both author and committer email.
The repository-local Git configuration pins that identity, automated checks validate reachable
history, and GitHub pull requests use rebase merging rather than merge or squash commits generated
from account profile metadata.

Reason: global Git configuration does not govern commits generated by GitHub and can vary across
development environments. Repository and CI enforcement prevents unrelated identities from
entering project history.
