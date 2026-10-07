# ForeView

*Understand, manage, and model your financial life. See where you are. Explore what's ahead.*

ForeView is a local-first personal and household financial management, analysis, and modelling
application. Its present focus is Canadian personal finance, tax, and retirement planning. It
consolidates accounts, balances, transactions, investment holdings, GICs, real estate, factual
income and expenses, and versioned public tax rules into a private SQLite runtime.

The project is under active development. Retirement planning is an important current use case,
not the permanent boundary of the application. Implemented capabilities and current limitations
are recorded in [Current state](docs/current-state.md).

## Shared project context

The repository is the durable handoff point for human contributors and coding agents:

- [Architecture](docs/architecture.md) describes the system that currently exists.
- [Design decisions](docs/decisions.md) records durable constraints and their rationale.
- [Current state](docs/current-state.md) identifies active work, known limitations, and next steps.
- [Contributing](CONTRIBUTING.md) describes contribution paths, project principles, and review
  expectations for code and non-code work.
- The [GitHub Project](https://github.com/users/colleeseum/projects/3) is the authoritative product
  roadmap and progress tracker.
- [Agent instructions](AGENTS.md) defines the workflow and engineering rules for coding agents.

Keep these documents aligned with executable code and tests. Focused contracts and requirements
remain beside their implementation or under `docs/` rather than being duplicated here.

## Important disclaimer

This software is for informational, planning, and modelling purposes only. Its calculations and
projections may be incomplete, inaccurate, outdated, or inappropriate for a particular situation.
Nothing it produces is financial, investment, tax, accounting, or legal advice. Independently
verify important results and consult an appropriately qualified professional before making
significant decisions.

Read the full [financial-planning disclaimer](DISCLAIMER.md), including its warranty and liability
limitations.

## Current capabilities

- Separate synthetic development and private production runtimes.
- Account, balance, transaction, holding, GIC, and real-estate tracking.
- PDF and CSV import adapters for supported financial institutions.
- Multiple independently authorized Questrade logins and account synchronization.
- Synthetic documents and a synthetic Questrade API for repeatable tests without private data.
- Annual federal, provincial, and territorial public-rule packages with source provenance,
  deterministic JSON, content hashes, and explicit runtime approval.
- Effective combined federal and provincial marginal rates for ordinary income.

## Modelling assumptions and rationale

Assumptions are kept explicit because values that look comparable can have materially different
tax, access, and ownership characteristics.

### Assets and liquidity

- **Gross assets are pre-tax values.** RRSP and similar registered balances are not reduced by an
  arbitrary tax percentage. Their eventual tax depends on the timing and amount of withdrawals,
  other income, province of residence, and future rules. An after-tax value belongs in a scenario
  projection, not in the factual asset register.
- **Liquidity distinguishes preferred funds from available reserves.** Non-registered liquid
  funds are shown separately from liquidity that also includes TFSA assets. This reflects the
  planning preference to preserve the TFSA unless it is needed, while still acknowledging that it
  is accessible.
- **Uninvested cash in registered investment accounts is reported separately.** It may require
  investment attention, but it is not equivalent to unrestricted household cash because removing
  it from an RRSP can create taxable income.
- **GIC and term-deposit liquidity depends on their terms.** Maturity dates, rates, and redemption
  restrictions are retained instead of treating every cash-like balance as immediately available.
- **A parent account balance may include or exclude its child GIC balances.** The account records
  this explicitly so consolidation does not double-count an inclusive balance or omit an additive
  child balance.
- **Real estate uses the current ownership-adjusted estimate as a factual asset value.** Principal
  residence status and adjusted cost base are retained, but future tax treatment and sale costs
  are deferred to projections because they depend on future events and rules.

### Balances and imports

- **Dated source balances take precedence when an institution supplies them.** When an export has
  transactions but no running balance, the application reconstructs balances from a known anchor
  and marks the opening balance explicitly. This avoids presenting a calculated history as if it
  came directly from the institution.
- **Original imported content and file hashes are retained.** Normalized records can therefore be
  traced to their source, and repeated files can be detected.
- **Institution parsers are format-specific.** A parser succeeding does not prove that the source
  statement is complete. Some providers expose cumulative or partial-period information rather
  than a complete transaction ledger.

### Tax rules and calculations

- **Annual official source artifacts and normalized rule packages are committed to Git.** This
  makes past calculations reproducible and avoids depending on a government archive during a
  future installation.
- **Downloading is not approval.** Each exact normalized package hash must be reviewed and
  approved in Settings. Review includes both numeric values and structural changes, such as added,
  removed, or changed credits, contributions, thresholds, phase-outs, surtaxes, or indexation
  mechanisms. A new concept may require code changes even when extraction succeeds.
- **Money and rates use decimal calculation contracts.** This avoids binary floating-point drift
  in rule and projection calculations. Existing factual SQLite `REAL` columns remain unchanged
  until a separate migration is justified.
- **The combined marginal-rate view currently models ordinary taxable income with the basic
  personal amount.** It includes the federal BPA phase-out and implemented jurisdiction-specific
  rules such as the Quebec abatement, Manitoba BPA phase-out, and Ontario surtaxes. It excludes the
  Ontario Health Premium and income-specific treatment for capital gains and dividends. It is a
  diagnostic view, not a complete tax return calculator.
- **Official government publications are authoritative inputs.** Independent references may be
  used to detect discrepancies, but they do not replace review of the official source.

These assumptions describe current behaviour, not permanent policy. Changes that affect results
should update this section and add or revise regression tests deliberately.

## Requirements

- Python 3.11 or newer. The current development environment uses Python 3.14.
- SQLite, provided by Python.
- A modern browser.

## Quick start with synthetic data

Create an isolated environment and install the application and development dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
```

Generate the fictional runtime and start the development server:

```sh
.venv/bin/python synthetic_runtime.py .runtime/dev
.venv/bin/python app.py --profile dev
```

Open <http://127.0.0.1:5124>. The development profile enables Flask debugging and automatic
reload, binds only to localhost, and contains invented data.

To add the synthetic Questrade synchronization scenario:

```sh
make load-questrade-dev
```

New synthetic runtimes include factual expense examples. To add those examples to an existing
synthetic development runtime without rebuilding it:

```sh
make load-expenses-dev
```

The expense loader refuses non-synthetic runtimes and is idempotent.

The loader refuses to run unless the selected runtime identifies itself as synthetic. It is
idempotent. An updated synchronization can be simulated with:

```sh
.venv/bin/python synthetic_questrade.py .runtime/dev --scenario updated
```

## Runtime profiles and private data

Source code and private runtime data are intentionally separate:

| Profile | Default location | Purpose |
| --- | --- | --- |
| `dev` | `.runtime/dev` | Invented data for development and tests |
| `prod` | `~/.local/share/retirement-finance/prod` | Private user data and credentials |

The `retirement-finance` runtime directory, `RETIREMENT_*` configuration names, and
`retirement-model-browser` package identifier predate the ForeView product name. They remain
unchanged for backward compatibility.

A runtime directory contains `finance.sqlite3`, `finance.config.json`, and may contain `locale.json` for the persisted interface-language preference. Start the private runtime
with:

```sh
.venv/bin/python app.py --profile prod
```

During local development against the private runtime, enable source reload without exposing the
interactive debugger:

```sh
.venv/bin/python app.py --profile prod --reload
```

Use `--data-dir /absolute/path/to/runtime` for another location. WSGI and other tooling may set
`FINANCE_DATA_DIR`; otherwise `FINANCE_PROFILE` accepts `dev` or `prod`. Use `--port` to override
the profile default. Every profile binds to `127.0.0.1` by default. To make a server reachable on
a trusted private network, opt in explicitly with `--host 0.0.0.0` and keep TLS configured.

The production profile disables the interactive debugger. TLS certificate and key paths are read
from its private configuration. Browser state-changing requests use CSRF tokens, but the
application does not yet authenticate users. Never expose the server to an untrusted network.

Do not commit or share runtime databases, imported statements, reference spreadsheets,
configuration files containing credentials, access tokens, or encryption keys. Do not archive the
complete working directory as a convenient way to share the source tree.

### Database migrations and backups

Startup applies numbered migrations recorded in the runtime database's `schema_migrations` table.
Applied migration files are append-only: add a new migration instead of editing an old one.

Monetary facts are authoritative in integer-cent columns and are converted through `Decimal`
before arithmetic. Legacy `REAL` columns remain temporarily for backward-compatible imports and
direct inspection, but application reads and aggregate calculations use the cent values.

Create a consistent backup of the database and private configuration before a migration or data
reload:

```sh
.venv/bin/python runtime_backup.py --profile prod backup /secure/path/finance-backup
```

The backup contains checksums and is validated with SQLite integrity and foreign-key checks.
Restore refuses to overwrite a runtime unless `--replace` is explicit. A replacement first creates
a sibling `pre-restore` safety backup of the current runtime:

```sh
.venv/bin/python runtime_backup.py --profile prod restore /secure/path/finance-backup --replace
```

Backup directories contain private financial data and credentials. Store them with the same access
controls as the live runtime.

## Questrade configuration

Copy the example configuration into the private runtime and generate local encryption and session
secrets:

```sh
mkdir -p ~/.local/share/retirement-finance/prod
cp -n finance.config.example.json ~/.local/share/retirement-finance/prod/finance.config.json
.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Configure one named `QUESTRADE_CONNECTIONS` entry per Questrade personal application. Different
family logins may have different Consumer keys and must be authorized separately. Set
`QUESTRADE_REDIRECT_URI` to the exact HTTPS callback registered with Questrade, for example:

```text
https://finance.example.com:5123/questrade/callback
```

Each sync re-reads at least the seven days before the previous sync of that account stopped, and
a full 30-day request when the last sync was more recent, which picks up activity posted late with
an earlier date. Already-imported activity is skipped. The
first sync of an account starts at the entry's optional `history_start` date (`YYYY-MM-DD`, for
example the date the account was opened) or, without one, about 16 months back. To recover
activity missing from an earlier period, for example when a reconciled balance no longer matches,
use **Re-fetch from** on the Connections page; activity already imported is skipped.

Questrade access and refresh tokens are encrypted before storage in SQLite. Preserve
`RETIREMENT_TOKEN_KEY` across restarts and backups. Losing it makes existing encrypted tokens
unusable. `RETIREMENT_APP_SECRET` protects application sessions and must also remain private.

## Updating public financial rules

Retrieve the current federal rules and the rules for every province and territory from configured
official government sources:

```sh
make update-public-rules
```

The current calendar year is selected automatically. Existing valid annual packages are skipped,
which makes the command suitable for a periodic scheduled job. Use an explicit historical year or
provider when needed:

```sh
.venv/bin/python update_public_rules.py --year 2025
.venv/bin/python update_public_rules.py --year 2026 --provider ca.qc
```

Use `--force` only to deliberately replace an existing annual package. Any content change creates
a new hash and invalidates the previous runtime approval.

Generated packages are stored under `public_rules/<year>/` with the original source artifacts,
checksums, provenance, and deterministic normalized JSON. After retrieval:

1. Review changes against the linked official publications.
2. Check for added, removed, or structurally changed rules, not only changed numbers.
3. Run the complete QA suite.
4. Commit the reviewed annual package.
5. Approve each exact package hash in the application Settings page.

## Quality assurance

Run the complete QA suite with:

```sh
make qa
```

It checks the Git diff for whitespace errors, then runs Ruff formatting and lint checks, JavaScript
tests and coverage, mypy, pytest with branch coverage, integration coverage, Bandit, and dependency
audits. Useful focused targets include:

```sh
make test
make diff-check
make coverage
make integration-coverage
make lint
make typecheck
make security
make audit
```

The enforced branch-coverage floor is 80%. Tests emphasize balances, imports, ownership,
authentication, external synchronization, and projections. Existing failing tests are treated as
evidence about behaviour and are not weakened merely to make a change pass.

## Architecture

The application uses explicit boundaries rather than placing every concern in Flask routes or a
single persistence module:

- `domain/`: financial domain objects and contracts.
- `repositories/`: SQLite persistence adapters.
- `services/`: application workflows.
- `institutions/`: one self-contained module per financial institution, with its parsers,
  import services, help, and connection behaviour. See [institutions/README.md](institutions/README.md).
- `institution_support/`: the institution contract, discovery, and document detection.
- `ingestion/`: import steps shared by institutions, such as PDF reading and raw-row storage.
- `projection/`: public-rule models, retrieval, and tax or projection calculations.
- `web/` and `templates/`: HTTP and presentation concerns.
- `public_rules/`: versioned, reviewable public data and source artifacts.

Projection algorithms are intended to be replaceable behind contracts so a timeline can use, for
example, a salary projection until retirement and a retirement-income strategy afterward.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution paths, project principles, financial-rule
expectations, testing requirements, and credit for substantive code and non-code contributions.

## License

This project is source-available for noncommercial use under the
[PolyForm Noncommercial License 1.0.0](LICENSE). Individuals may use, modify, fork, and redistribute
the original Mindstep software and documentation for noncommercial purposes subject to the
license terms. The license also permits the qualifying noncommercial organizational uses that it
identifies.

The PolyForm license does not replace the ownership or terms of government source documents,
third-party material, imported data, or artifacts that incorporate externally owned material.
Their applicable ownership, notices, and license terms remain in effect merely because they are
present in or used by this repository.

Commercial use requires a separate written license from Mindstep Corporation. For commercial
licensing inquiries, contact [info@mindstep.ca](mailto:info@mindstep.ca). See
[LICENSING.md](LICENSING.md) for details.
