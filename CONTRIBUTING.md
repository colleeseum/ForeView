# Contributing to ForeView

Thank you for your interest in contributing.

This project is a local-first personal and household financial
management, analysis, and modelling application. Its current development
is strongly focused on Canadian personal finance, tax, and retirement
planning, but those are current priorities rather than permanent
boundaries.

The project is intended to be useful beyond a single financial-planning
workflow. Over time it may grow to cover additional areas of personal
and household finance, additional planning problems, and additional
jurisdictions.

Contributions are therefore welcome from software developers, tax and
financial-domain contributors, testers, technical writers, designers,
and users with useful financial knowledge or experience.

A contribution does **not** need to contain code to be valuable.

## Ways to contribute

Useful contributions may include:

-   source code, bug fixes, refactoring, tests, and user-interface
    improvements;
-   tax, accounting, investment, pension, retirement, estate, insurance,
    budgeting, or other financial research;
-   validation of calculations, financial models, and planning
    assumptions;
-   corrections or updates to public tax rules, thresholds, credits,
    contribution limits, benefits, or similar data;
-   identification of financial, tax, accounting, or modelling edge
    cases;
-   comparison of application results against authoritative or
    independently calculated reference cases;
-   support for financial institutions, data formats, and import
    workflows;
-   documentation, examples, usability, and accessibility improvements;
-   reproducible bug reports and synthetic test cases;
-   proposals for useful new personal or household financial
    capabilities.

If you have relevant domain knowledge but do not write software, you are
still encouraged to contribute. A well-supported correction to a tax
rule, an explanation of a financial edge case, or an independently
validated calculation can be as valuable as a code change.

## Contributions that expand the project

Contributions do not need to fit the application's current
retirement-planning focus.

Proposals that broaden the application into useful personal or household
financial capabilities are welcome when they fit the project's general
principles of privacy, traceability, explicit assumptions, auditable
calculations, and maintainable architecture.

Possible future areas might include budgeting, cash-flow analysis, debt
management, estate planning, insurance analysis, investment analysis,
tax optimization, additional retirement strategies, additional
jurisdictions, or capabilities not currently anticipated.

These examples are illustrative, not a roadmap or limitation on scope.

Large additions should normally begin with a discussion or issue so that
the problem, intended users, data requirements, assumptions, and
architectural implications can be understood before substantial
implementation work begins.

## Tax and financial contributions

Financial behaviour can materially affect the decisions someone makes
using the application. Domain contributions should therefore be
reviewable and evidence-based.

Whenever practical:

1.  Identify the jurisdiction and applicable year or effective period.
2.  Describe the rule, calculation, assumption, interpretation, or
    behaviour being proposed or corrected.
3.  Provide an authoritative source when one exists.
4.  Explain interpretations that are not directly stated by the source.
5.  Identify important exceptions, thresholds, or boundary conditions.
6.  Provide examples that can be independently checked and, where
    appropriate, converted into automated tests.

The authoritative source depends on the jurisdiction and subject matter.
Government departments, tax authorities, regulators, legislation,
official pension administrators, and other primary sources should
normally take precedence over secondary summaries.

For the project's current Canadian work, this commonly means sources
such as the Canada Revenue Agency and the applicable provincial or
territorial authority. For Québec tax matters, for example, Revenu
Québec is an important authoritative source alongside applicable federal
sources.

Independent calculators, professional publications, financial
institutions, and other secondary references can be useful for
validation and for identifying discrepancies, but they should not
silently replace an authoritative source when one is available.

If a question involves professional judgment or a modelling choice
rather than a deterministic rule, identify it as an assumption or
interpretation rather than presenting it as established fact.

## Credit for contributions

Substantive contributions are eligible for project credit whether or not
they contain code.

This includes meaningful work involving:

-   software development;
-   testing and quality assurance;
-   tax or regulatory research;
-   financial-domain research and analysis;
-   calculation or model validation;
-   documentation;
-   design and usability;
-   supported bug reports and edge cases;
-   data or rule validation;
-   other substantive contributions to the project.

Where practical, accepted contributions should preserve attribution
through Git history, pull requests, issue discussions, documentation,
acknowledgements, or another appropriate project mechanism.

Contributor credit recognizes the work contributed. It does **not**
imply that a contributor endorses the project as a whole, accepts
responsibility for other portions of the project, or assumes
professional responsibility for the application's financial, tax,
accounting, investment, legal, or other outputs.

Likewise, the professional qualifications of an individual contributor,
if any, do not turn the project or its output into professional advice.

## Before starting substantial work

Small corrections, documentation improvements, narrowly scoped tests,
and clearly isolated bug fixes can generally be submitted directly.

For a substantial feature, architectural change, new financial model,
new jurisdiction, or change that can materially alter calculated
results, please open or reference an issue first.

Early discussion is particularly useful when a proposal introduces:

-   a new type of financial record;
-   a new projection or optimization model;
-   a new external data source;
-   a new jurisdiction or regulatory regime;
-   a modelling assumption that could reasonably be implemented in more
    than one way;
-   a change to persisted data or historical interpretation;
-   a new major application capability.

The goal is not to discourage experimentation. It is to avoid embedding
an accidental product or financial-policy decision deep in the
implementation before it has been recognized as a decision.

Review the repository's architecture, design decisions, current-state
documentation, and contributor/agent guidance before making broad
changes.

## General design principles

The application should remain understandable and auditable as it grows.

Contributions should generally preserve these principles:

-   **Local-first and privacy-conscious.** Private financial information
    belongs in the user's runtime, not in the source repository.
-   **Facts and assumptions are different things.** Historical financial
    facts should remain distinguishable from forecasts, scenarios,
    estimates, and modelling assumptions.
-   **Provenance matters.** Imported or externally sourced information
    should remain traceable to its origin when practical.
-   **Historical meaning should be preserved.** A later classification
    or rule change should not silently rewrite the meaning of historical
    records.
-   **Unknown is not zero.** Missing information should remain
    distinguishable from an explicit value of zero.
-   **Financial policies should be explicit.** Do not hide an arbitrary
    financial or modelling decision inside implementation details.
-   **Calculations should be reproducible.** Given the same facts,
    assumptions, rules, and software version, important calculations
    should be explainable and repeatable.
-   **Public rules should be versioned.** Rules that change by year or
    effective date should preserve their historical versions.
-   **Architecture should remain modular.** New capabilities should use
    appropriate domain, persistence, service, integration, and
    presentation boundaries rather than accumulating special cases.
-   **Evidence should survive normalization.** A normalized value should
    not unnecessarily destroy the ability to understand where it came
    from.
-   **Money deserves deliberate handling.** Avoid floating-point
    behaviour or rounding policies that can silently alter authoritative
    monetary values.
-   **Persisted data deserves compatibility.** Applied database
    migrations are append-only. Add a new migration rather than changing
    one that may already have been applied.

These are design principles rather than restrictions on what financial
capabilities the project may eventually support.

## Private and synthetic data

Do not commit or submit private financial information.

This includes, among other things:

-   real bank or investment statements;
-   account numbers;
-   transaction histories containing personal information;
-   tax returns;
-   personal identity information;
-   authentication tokens;
-   passwords or encryption keys;
-   production runtime databases;
-   private configuration or credentials.

Tests, examples, screenshots, fixtures, and bug reproductions should use
synthetic data unless there is a compelling and safe reason otherwise.

If a parser or import workflow needs a regression case, create the
smallest synthetic document or fixture that reproduces the relevant
behaviour without exposing personal or confidential information.

Do not archive or submit an entire private working environment merely as
a convenient way to provide source code.

## Changes to financial calculations

Changes that affect financial results deserve additional scrutiny
because apparently small implementation choices can materially change an
output.

Such changes should, where applicable:

-   document the rule or assumption being implemented;
-   identify the authoritative source when one exists;
-   preserve the applicable jurisdiction and effective period;
-   include regression tests;
-   exercise important thresholds and boundary conditions;
-   use the project's established monetary and decimal calculation
    contracts;
-   distinguish unavailable information from an explicit zero;
-   define rounding deliberately;
-   avoid silently choosing a financial policy when requirements allow
    multiple reasonable interpretations.

If the correct behaviour depends on a product or modelling decision,
raise that decision explicitly rather than selecting an arbitrary
interpretation merely to complete the implementation.

## Public financial rules

Public rules used by calculations should remain reproducible and
reviewable.

When adding or changing public rules:

1.  Prefer the applicable authoritative source.
2.  Record enough provenance to identify what was used.
3.  Preserve the effective year or period.
4.  Review structural changes as well as changed numeric values.
5.  Do not overwrite historical rules merely because newer rules are
    available.
6.  Add or update tests for affected calculations.
7.  Run the applicable quality-assurance suite.

Retrieval, parsing, and correctness are separate concerns. A value
successfully downloaded or parsed from a source is not automatically
considered reviewed or correct.

The project's current Canadian public-rule framework follows these
principles, but they are intended to remain applicable if other
jurisdictions are added later.

## Imports and external financial data

Imported facts should remain traceable to their source.

Where practical, import workflows should preserve enough information to
answer questions such as:

-   Which source produced this record?
-   When was it imported?
-   Which parser or integration interpreted it?
-   Can the original evidence be identified?
-   Could this information already have been imported from another
    source?
-   Was a value reported by the source or inferred by the application?

A parser successfully reading a document does not prove that the
document is complete or that every interpretation is correct.

Repeated imports, overlapping evidence, and partial statements should be
handled deliberately rather than silently creating duplicate financial
facts.

## Software contributions

Follow the repository's existing architectural boundaries and
conventions.

The application separates concerns across areas such as domain models,
repositories, services, institution integrations, ingestion,
calculations/projections, web routes, and templates. New work should
extend those boundaries where appropriate instead of bypassing them for
convenience.

New institution support should normally be implemented using the
institution integration contract rather than by adding
institution-specific conditions throughout unrelated application code.

Prefer small, understandable interfaces and tests around financial
behaviour. A sophisticated calculation that cannot be explained or
verified is difficult to trust.

## Testing and quality assurance

Before submitting a code change, run:

``` sh
make qa
```

The complete QA suite includes formatting and lint checks, JavaScript
tests, type checking, Python tests and coverage, integration coverage,
security checks, and dependency audits.

Useful focused targets include:

``` sh
make test
make diff-check
make coverage
make integration-coverage
make lint
make typecheck
make security
make audit
```

Do not weaken or remove a legitimate test merely to make a change pass.

If an existing expectation is no longer correct because an underlying
requirement has deliberately changed, explain the requirement change and
update the implementation, tests, and relevant documentation together.

Tax and financial-domain contributors are **not** expected to become
software developers merely to participate. Contributors who cannot run
the application or write automated tests are welcome to provide
research, references, calculations, examples, or review findings. An
accepted domain contribution can subsequently be translated into code
and executable tests.

## Pull requests

A pull request should make it reasonably easy for another contributor to
understand what changed and why.

Where applicable, include:

-   a concise description of the problem or goal;
-   the relevant issue;
-   important design or modelling decisions;
-   authoritative sources for tax, regulatory, or financial-rule
    changes;
-   tests or independent validation performed;
-   screenshots for meaningful UI changes;
-   known limitations;
-   unresolved questions or assumptions.

Keep unrelated changes separate where practical. Avoid generated private
data, local runtime files, credentials, or unrelated formatting churn.

## Documentation

Code, tests, financial behaviour, and documentation should describe the
same system.

Changes that alter architecture, supported workflows, financial
behaviour, assumptions, known limitations, or major capabilities should
update the relevant shared documentation.

Documentation should explain not only **what** the application
calculates, but---where important---**why** the calculation behaves that
way and what rule, evidence, or assumption supports it.

## License and contribution terms

The project is source-available for noncommercial use under the PolyForm
Noncommercial License 1.0.0. See `LICENSE` and `LICENSING.md` for the
applicable terms.

By submitting a contribution, you represent that you have the right to
submit the material and that the project may distribute your accepted
contribution as part of the project under its applicable licensing
terms.

Do not submit third-party code, proprietary financial material,
copyrighted publications, confidential information, or other content
unless its license and permitted use allow its inclusion.

Commercial licensing is handled separately by Mindstep Corporation.

## Professional responsibility and disclaimer

This software is intended to assist with financial information,
analysis, modelling, and planning. It is not a substitute for
professional financial, investment, tax, accounting, legal, insurance,
or other professional advice.

The project can contain mistakes. Tax and financial rules can be
complicated, change over time, depend on individual circumstances, and
sometimes require interpretation.

Contributors are encouraged to improve accuracy and identify
limitations, but acceptance of a contribution does not constitute
professional certification of the software or its results.

See `DISCLAIMER.md` for the project's full disclaimer, warranty, and
liability terms.

## Collaboration

Be specific, evidence-based, and constructive.

Financial and tax questions can have multiple plausible interpretations,
particularly when legislation, administrative guidance, product
behaviour, and planning assumptions interact. When contributors
disagree, prefer authoritative evidence, reproducible examples, clearly
stated assumptions, and tests over unsupported assertions.

It is entirely acceptable for a contribution to identify an unresolved
question rather than pretending that certainty exists.

The objective is not merely for the software to produce an answer. The
objective is for users and contributors to be able to understand **what
the answer represents, where its inputs came from, and what rules or
assumptions produced it**.
