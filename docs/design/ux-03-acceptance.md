# UX-03 cross-application acceptance

UX-03L (#106) integrates the [approved A / Sage brief](ux-03a/index.html),
the [shared foundation](ui-foundation.md), workspace workflow checks and visual
evidence. This is an acceptance record, not a second roadmap or an assertion that
the separate retirement-planning engines exist.

## Delivery and evidence traceability

| Recommendation / workspace | Completed delivery | Evidence and executable contract |
| --- | --- | --- |
| Source reconciliation, alternatives, selected Sage direction | [#95 / PR #107](https://github.com/colleeseum/ForeView/pull/107) | [A brief and original baseline](ux-03a/index.html) |
| Semantic tokens, readable type, controls, feedback, native dialogs | [#96 / PR #108](https://github.com/colleeseum/ForeView/pull/108) | [Foundation](ui-foundation.md); `tests/browser/ui-primitives.mjs`, `tests/js/dialog.test.mjs` |
| Responsive navigation, module access and active-page semantics | [#97 / PR #109](https://github.com/colleeseum/ForeView/pull/109) | [Navigation](navigation.md); `tests/browser/navigation.mjs` |
| Factual overview, missing versus zero, loading/error recovery | [#98 / PR #110](https://github.com/colleeseum/ForeView/pull/110) | [Dashboard](dashboard.md); `tests/browser/dashboard.mjs` |
| Assets, GICs, property, ownership, density, Add/Edit dialogs | [#99 / PR #111](https://github.com/colleeseum/ForeView/pull/111) | [Assets](assets.md); `tests/browser/assets.mjs` |
| Transaction tables, import selection and reconciliation | [#100 / PR #113](https://github.com/colleeseum/ForeView/pull/113) | [Transactions](transactions.md); `tests/browser/transactions.mjs` |
| Income snapshots, source provenance, corrections and source review | [#101 / PR #114](https://github.com/colleeseum/ForeView/pull/114) | [Income](income.md); `tests/browser/income.mjs` |
| Dated expenses, categories, seasonal estimates and statement imports | [#102 / PR #115](https://github.com/colleeseum/ForeView/pull/115) | [Expenses](expenses.md); `tests/browser/expenses.mjs` |
| Existing employment projection, assumptions and disclaimer | [#103 / PR #117](https://github.com/colleeseum/ForeView/pull/117) | [Employment](employment.md); `tests/browser/employment.mjs` |
| People, Connections, public rules, settings, About and Disclaimer | [#104 / PR #119](https://github.com/colleeseum/ForeView/pull/119) | [Administration](administration.md); `tests/browser/administration.mjs` |
| Full help, contextual destinations, tooltips, provider fallback | [#105 / PR #120](https://github.com/colleeseum/ForeView/pull/120) | [Help](help.md); `tests/browser/help.mjs` |

Each linked workspace contract includes its synthetic before/after evidence.
Those captures are reviewed examples, not automatically accepted pixel goldens.
The A baseline predates the feature migrations and uses its original named
viewports; it is not a byte-for-byte reference for every final viewport.

## Integrated automated matrix

`tests/test_ui_primitives.py` runs all workspace workflow verifiers, then the
read-only tour in `tests/browser/acceptance.mjs`, against a disposable synthetic
runtime. The tour visits all twelve existing page routes in en-CA, fr-CA and a
registered synthetic RTL locale with French fallback:

- 1440 x 1000 and 1280 x 900 desktop viewports;
- 390 x 844 and 320 x 800 narrow viewports;
- 640 x 450 half-width reflow viewport, supplementing the named matrix.

For every page/viewport it checks document, main and inner workspace fit without
suppressing locally scrollable financial tables. Every visible table must be
contained by a labelled keyboard-scroll region. It also checks primary control
targets, actual rendered samples of normal-text contrast at 4.5:1, selected locale,
resolved message keys, full-help modal entry, visible Close, Escape and focus return.
Contrast samples include headings, navigation headings, enabled primary buttons
and shared table headers where present. Foreground alpha, background alpha and
element/ancestor group opacity are composited before measuring contrast.
Synthetic browser regressions verify rejection of hidden Close controls,
workspace-only overflow, uncontained tables and faded text. Close must be both
visible and intersecting the viewport, including at 450px height.
This is not exhaustive pixel sampling or
a WCAG certification. The original below-target sidebar pair is a unit-test
regression for the contrast calculation.

The tour rejects mutation requests and compares dashboard, accounts, transactions
and annual projection API read models before/after. Its generated locale manifests
record page/viewport dimensions, screenshot names, sample counts and minimum
contrast, not private financial payloads. Narrow retained captures collapse the
menu to expose content; the expanded-menu layout assertions still run first.
Feature workflow verifiers separately
exercise deliberate mutations, retained input, busy guards, recoverable errors,
source semantics and unchanged-value invariants within disposable data.

A browser-only dashboard fixture adds a large amount, a negative amount, zero,
missing data and long English source evidence. It verifies locale-native CAD and
date output independently with Intl, preserved source-language metadata, card fit,
and 200% root-text reflow without writing those values to the runtime. This is not
a substitute for manually checking native browser zoom across all workflows.

Functional state coverage remains executable rather than inferred from captures:

| State or boundary | Verification |
| --- | --- |
| Loading, empty, zero, unavailable and failed dashboard reads | Dashboard browser verifier and dashboard DOM tests |
| Dirty, unchanged-disabled, validation, busy save, cancel, committed-save/read-refresh separation | Assets, Transactions, Income, Expenses and Employment browser/DOM suites |
| Duplicate imports, source precedence, overlaps, corrections and reconciliation prompts | Feature browser workflows plus Python route/service integration tests |
| Localized money/dates/numbers and per-field source language | Shared formatter tests, localized browser workflows, Income/import/help verifiers |
| Category order, search/no-results, native modal stacking and Tab/Escape | Help and foundation browser verifiers plus help/dialog DOM tests |
| Read-only connection status/retry, exact rule-hash approval and legal access | Administration browser/DOM and route tests |

## Scope dispositions and remaining limitations

- Small / Normal / Large text-size persistence is explicitly separate work in
  [#118](https://github.com/colleeseum/ForeView/issues/118), following the maintainer
  decision during #104. Its subsequently approved scale and preference contract
  are recorded in the [foundation](ui-foundation.md#text-size-preference).
  It is not waived, implemented or completed by this validation issue.
- A genuine parsed transaction preview remains
  [#112](https://github.com/colleeseum/ForeView/issues/112). The current file-selection
  review must not be described as a non-mutating parsed-data preview.
- Fractional rate-input precision remains the independently tracked financial
  defect [#116](https://github.com/colleeseum/ForeView/issues/116). UI validation
  does not certify that conversion path or authorize a hidden calculation fix.
- Remaining jurisdiction-label localization and About institution display-name
  language handling are tracked in [#121](https://github.com/colleeseum/ForeView/issues/121),
  added to the Project under parent #94. The missing-key check does not prove
  that every raw reference label has been localized. This validation does not
  silently change provider identity or public-rule packages to address them.
- Retirement baselines, benefit/withdrawal strategies, scenario comparison and
  real/nominal planning remain in the separately linked backlog in the A brief.
- Automated browser checks use Chromium. The half-width viewport is a reflow
  check, not automation of browser-chrome zoom. Native browser zoom, Safari/Firefox
  and real assistive-technology verification remain explicit manual acceptance
  work. Synthetic RTL checks layout/fallback, not a completed Arabic translation.

## Verification and maintainer acceptance

On 27 October 2026, `make qa` passed: 608 Python tests with branch coverage,
167 integration tests and 111 JavaScript tests, plus formatting, type, identity,
license, security and dependency gates. JavaScript branch coverage was 85.72%;
no coverage threshold or existing financial expectation was reduced.
The final focused browser run passed all four tests after regenerating narrow
captures with collapsed navigation; no application behavior changed for capture.
The review follow-up passed four focused tests in 191.45 seconds with the
stronger visibility, compositing, workspace-overflow and table-containment gates.

The integrated tour passed 180 page/viewport combinations, sixty per locale.
The minimum sampled normal-text contrast was 5.245:1. Each tour recorded zero
mutation requests and unchanged read models. The large/signed/zero/missing amount,
localized date/currency, source-language and 200% dashboard-text checks passed.

Full measurement manifests: [English](ux-03l/evidence/en-CA-acceptance.json),
[French](ux-03l/evidence/fr-CA-acceptance.json),
[synthetic RTL](ux-03l/evidence/ar-XB-acceptance.json).
The manifests enumerate all generated captures. The repository retains the
representative subset below, not every generated PNG; rerun the synthetic test
to regenerate the full set in pytest's temporary evidence directory.

| Surface | Retained final capture |
| --- | --- |
| Dashboard | [English desktop](ux-03l/evidence/en-CA-1440x1000-dashboard-acceptance.png) |
| Assets | [French narrow](ux-03l/evidence/fr-CA-390x844-assets-acceptance.png) |
| Transactions | [RTL narrow](ux-03l/evidence/ar-XB-320x800-transactions-acceptance.png) |
| Income | [French narrow](ux-03l/evidence/fr-CA-320x800-income-acceptance.png) |
| Expenses | [French narrow](ux-03l/evidence/fr-CA-390x844-expenses-acceptance.png) |
| Employment | [English desktop](ux-03l/evidence/en-CA-1280x900-employment-acceptance.png) |
| People | [French narrow](ux-03l/evidence/fr-CA-390x844-people-acceptance.png) |
| Connections | [English desktop](ux-03l/evidence/en-CA-1280x900-connections-acceptance.png) |
| Public rules | [French narrow](ux-03l/evidence/fr-CA-320x800-rules-acceptance.png) |
| Application settings | [RTL narrow](ux-03l/evidence/ar-XB-320x800-settings-acceptance.png) |
| About | [English desktop](ux-03l/evidence/en-CA-1440x1000-about-acceptance.png) |
| Disclaimer | [French navigation, English legal text](ux-03l/evidence/fr-CA-390x844-disclaimer-acceptance.png) |
| Help | [Provider article and tooltip index](help.md) |
| Stress values | [English](ux-03l/evidence/en-CA-320-dashboard-stress.png), [French](ux-03l/evidence/fr-CA-320-dashboard-stress.png), [RTL](ux-03l/evidence/ar-XB-320-dashboard-stress.png) |
| 200% dashboard text | [English](ux-03l/evidence/en-CA-320-dashboard-text-resize.png), [French](ux-03l/evidence/fr-CA-320-dashboard-text-resize.png), [RTL](ux-03l/evidence/ar-XB-320-dashboard-text-resize.png) |

The maintainer reported completion of the requested manual zoom/keyboard check
in **Chrome**, following review of the Assets page at 200% browser zoom and the
table/editor access checks. Browser version, platform and manual language coverage
were not specified. This records that scoped manual check, not exhaustive manual
verification of every matrix combination. Safari, Firefox and screen-reader
verification have not been reported.

The manual checklist remains available for repeat checks and other environments:

1. Visit Assets, Income and Expenses in English/French. Reach the last table
   columns through local scrolling, without clipped amounts or lost provenance.
2. Open an editor and full help using the keyboard. Check forward/reverse Tab,
   reachable actions, Escape and return to the originating control.
3. Read a long provider article on a narrow window. Check Search and Close remain
   reachable, and the original source language is not misrepresented.
4. Record browser/platform and any assistive-technology checks actually performed.
   Do not claim Safari, Firefox or screen-reader verification from Chromium output.

The issue remains open until its completing PR merges. Parent #94 remains open
while required children, including #118 and #121, are outstanding or exclusions have not
been explicitly approved.
