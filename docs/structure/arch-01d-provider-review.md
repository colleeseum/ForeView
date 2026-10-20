# ARCH-01D: Provider organization and shared contracts

Issue: [#72](https://github.com/colleeseum/ForeView/issues/72), parent
[#68](https://github.com/colleeseum/ForeView/issues/68).

Review baseline: `3dc7edbcbd873571bb94fed26830e12c8f785145`, 2026-10-20.
Outcome: retain the current packages and capability-specific contracts, with no runtime change.

## Scope and method

Inspected the registries and provider dataclasses in `account_types/`, `expense_sources/`,
`income_sources/`, `institution_support/`, `institutions/`, `public_pension_sources/` and
`tax_notices/`, their presentation and ingestion consumers, and relevant tests. Compared discovery,
construction lifetime, validation, lookup/detection results, output types, metadata and help.
Public-rule providers under `projection/rule_update/` are outside this review's scope; this
decision does not assess their organization, protocol or registration/execution policies.
The earlier [organization plan](arch-01a-plan.md) remains the pinned pre-move inventory, not a
description of current file locations.

## Existing boundaries

| Family | Registration and lifetime | Responsibility and material differences |
| --- | --- | --- |
| Account types | Sorted package discovery; a fresh registry per call | Classification, tax treatment, liquidity and supported account features. Exact-key `get`/`find`; no document parser, CalVer or translation mapping in this contract. |
| Institutions | Sorted package discovery; factories run on each call | Normalized aliases, multiple document importers, CSV fallback priority, balances, repairs and optional live connections. Validates name/importer collisions and CalVer. Rebuilding preserves patched importer bindings. |
| Expense sources | Package discovery at module initialization; retained registry | Byte detection and typed expense evidence, not account persistence. Rejects unknown/ambiguous formats with coded validation errors; validates keys, names, versions and duplicate keys. Discovery does not explicitly sort or reject modules without factories. |
| Income sources | Explicit ordered construction at module initialization | Typed annual-return parsing and source labels. Optional detector; no match is a coded validation failure. Explicit key lookup is also supported. |
| Tax notices | Explicit ordered construction at module initialization | Typed assessed amounts and registered-plan-room facts. No match returns `None` so the combined income import can try another family. Ambiguous matches raise `ValueError`. |
| Public pension sources | Explicit ordered construction at module initialization | Typed earnings histories and benefit estimates. No match returns `None`; ambiguous matches raise `ValueError`. There is no account importer or connection capability. |

Evidence: each family's `registry.py` and provider dataclass; institution importer/connection
contracts under `institution_support/`; orchestration in `web/income_routes.py` and
`services/imports/`. The income preview tries notices, then pension statements, then returns.
Changing all detectors to one failure policy would therefore change that workflow.

The six registry modules do not directly import one another. Cross-family composition belongs to
HTTP/presentation adapters and workflow coordinators. Institution parsers, importers, raw-source
tags and live connections remain cohesive inside their institution packages. No common parent
directory is required to establish these boundaries.

## Actual duplication and existing reuse

- Three registries scan modules using `importlib`/`pkgutil` and look for `provider()` factories.
  This is repeated mechanism, but ordering, ignored modules, missing-factory handling and factory
  lifetime differ. A generic loader would need explicit policies and equivalent tests, not just
  replacement of identical code. Performance was not benchmarked; no performance justification
  for consolidation is claimed.
- Income, notice and pension registries have short, similar detector loops. Their no-match
  behavior, optional detectors, exception codes and result types differ. Expense detection adds
  its own diagnostics and validation contract.
- Provider dataclasses repeat `key`, `display_name`, version/help and optional translation fields
  where applicable. These fields do not imply a common parser or persistence interface.
  An institution importer writes through repositories; a document-source parser returns typed
  evidence; an account type classifies an asset. A universal base would obscure that distinction.
- CalVer validation already reuses `domain/calver.py`. Account types do not currently declare
  versions. Introducing versions there would be a product/contract change, not deduplication.
- Translation field resolution already reuses `localization/provider_content.py` through
  `localized_fields`. `web/localization.py` adapts it to HTTP/provider presentation. Provider-owned
  translations remain separate from original source identifiers and evidence.
- `web/help_routes.py` already adapts the different provider shapes into common article/category
  output and applies the shared fallback resolver. Its source-specific article construction
  supplies different categories, keywords, source labels and institution topic hierarchy. This
  is presentation adaptation, not proof that the domain provider contracts should be merged.
- Transaction ingestion already shares PDF reading, row writing, matching, hashing and
  reconciliation components under `ingestion/`. These are operational reuse boundaries, unlike
  a generic registry that merely shares field names.

## Decision and alternatives

Retain the seven package roots and the current registry/provider interfaces. Do not introduce a
`providers/` umbrella, universal provider base, common registry or new discovery framework in
ARCH-01D. Keep institution-specific modularity and existing shared ingestion/presentation helpers.

A directory-only move would require coordinated import/discovery changes, test updates and
verification of provider-adjacent help-resource paths without removing duplicated behavior or
improving an observed dependency boundary. Combining registry policies would be a behavioral
refactor, unlike the accepted browser/service organization batches. Small repeated loops alone
do not justify that scope.

A narrowly scoped discovery or document-detection helper remains a possible later proposal,
not an approved implementation. Reconsider only when a concrete extension or repeated defect
demonstrates the benefit, with explicit lifetime/order/failure policies, typed results, preserved
patch behavior and regression tests. Do not couple unrelated financial interfaces to achieve it.

## Limitations and findings outside this delivery

Not every difference above has an established historical rationale. In particular, expense
discovery's permissive factory handling and lack of explicit sorting, and unequal validation of
duplicate/blank identifiers across explicit document registries, are observed inconsistencies,
not assertions that these policies are intentional or desirable. Changing them needs focused
requirements and compatibility tests; this review does not silently standardize them.

Institution About labels still bypass provider translation resolution, and account types lack
the optional translation field used by other provider contracts. The former is already recorded
in current-state documentation; neither requires a package relocation to address. This review
does not claim localization is complete.

The review is based on tracked built-in implementations and synthetic tests. It does not establish
compatibility with untracked third-party plugins or predict future provider requirements.

## Verification and change boundary

Relevant evidence is exercised by `tests/test_institution_registry.py`,
`tests/test_account_type_registry.py`, `tests/test_expense_source_registry.py`,
`tests/test_service_layout.py`, provider presentation/localization tests and help/import route tests.
The service-layout suite checks fresh-process startup and retained document-parser identity.
No new tests or changed expectations are needed for this documentation-only outcome.

No provider, registry, runtime, schema, migration, API, source label, version, translation or help
content is changed by this delivery. Synthetic development-tool organization is outside this
decision's scope.
