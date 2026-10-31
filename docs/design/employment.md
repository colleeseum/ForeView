# Employment projection workspace

UX-03I (#103) adopts Sage styles for the existing employment and disposable-income
projection. It does not implement a retirement engine, scenario comparison, real/nominal
conversion or a different factual anchor. The API, Decimal calculations, rule approvals,
retirement-date proration, schema and saved-scenario payload contracts are unchanged.

## Presentation and interaction

Projection HTTP rate inputs use millionth-rate precision independently of cents-based
monetary inputs (#116). Settings, annual overrides, saved drafts, clones with drafts
and household spending growth retain fractional-percent assumptions. Non-finite or
malformed rates fail with localized validation before committing; failed drafts and
clones roll back atomically. Existing stored assumptions are not rewritten.

Factual salary-anchor outputs remain read-only and link to Income. Scenario assumptions,
historical actuals and calculated estimates retain separate sections. Annual overrides in expandable yearly details
have explicit labels, year/field accessible names and a reset action; changing an input
does not recalculate or persist until Save. The result table retains source/rule-year
information and is contained in a captioned, keyboard-focusable scroll region. The
financial-planning disclaimer remains visible with access to the authoritative full text.

Person and household selection uses ordinary pressed-state buttons rather than an
incomplete ARIA tab widget. Save As uses the shared native modal controller with visible
Cancel, initial name focus, keyboard containment and focus return. Pending reads/writes
disable conflicting controls and prevent repeated mutations or modal dismissal.

Personal assumptions/annual overrides and household spending use separate existing
endpoints. While one editor is dirty, the other is disabled until Save or Discard;
Save As is unavailable for an unsaved spending draft because its endpoint does not
accept that draft. This avoids silently losing the other editor's work during reload.
Global Save applies to personal inputs; spending retains its own explicit save action.

Validation failures retain the draft. A committed mutation followed by a failed read is
reported as saved with unavailable results, not as a rejected write. Old results are
cleared and recovery repeats only the read, preserving the selected or newly cloned
scenario ID. Calculation warnings remain visible even when the save itself succeeded.
An unchanged Save As uses the clone-only request rather than resubmitting stored
personal settings. A dirty personal draft still uses the existing draft contract.
The existing HTTP rate-rounding limitation for edited assumptions is tracked in #116;
this presentation change does not change that financial input contract.

## Verification

DOM regressions retain existing payload and monetary assertions and cover pending-write
guards, rejected-draft retention, malformed-response handling and read-only recovery.
The clone fixture shims native dialog methods rather than a legacy backdrop lifecycle.

Chromium acceptance uses the existing disposable synthetic runtime in English, French
and synthetic RTL. It checks desktop/mobile layout, native-dialog keyboard behavior,
disclaimer access, unchanged annual results after navigation and an unchanged-input
clone, scenario isolation, assumptions, retirement-date proration, annual override
save/reset, household spending and failed-read recovery. Existing route/service tests
remain authoritative for financial formulas and exact results.

Before-state screenshots are under `ux-03a/baseline/*-employment.png`.
After-state evidence:

- [English desktop](ux-03i/evidence/en-CA-1280-employment.png)
- [French mobile](ux-03i/evidence/fr-CA-390-employment.png)
- [Synthetic RTL](ux-03i/evidence/ar-XB-320-employment.png)

## Contextual icon actions (UX-05F, #138)

Annual overrides use the shared Reset icon instead of a close-shaped glyph. Its
localized name includes the specific field and year, distinguishing multiple resets
in the same row. The Override badge remains visible. Refreshed controls retain the
existing `.salary-use-default` selector, year/field hooks, deferred reset payload and
draft locking. Delegated tooltips cover their keyboard and pointer interactions.

Save As uses the shared Close icon; View, Discard, Save, Save As, spending Save and
Cancel retain explicit labels. Calculations, scenario cloning, dirty-state isolation,
financial values, annual input sizes and read-only recovery retain their contracts.

## Summary and yearly details (UX-06, #146)

The default personal table shows Year, Gross and Disposable income, with a yearly
expand/collapse action. Household summaries also show planned Expenses and Surplus /
deficit. Disposable income is visually emphasized and kept visible without horizontal
scrolling. Narrow layouts prioritize Year and Disposable; Gross and household spending
remain available in the expanded details. Historical and projected sections stay separate.

Each year's details retain every annual input, payroll/tax breakdown, age and rule/source
information from the previous wide table. Editable fields reserve a consistent status
line for Calculated default or Override plus Reset; override controls do not increase
summary-row height. Values and save/reset payloads are unchanged.

Expansion is presentation-only. It hides or reveals existing DOM nodes without fetching,
recalculating, saving or discarding drafts. Open years are retained in memory per scenario
and person/household across read refreshes and Save; a full page reload starts collapsed.
Changing viewport width only updates column spans, preserving field values and focus.
Expansion remains available while a spending draft locks personal inputs. The overall
pending-request guard still applies while a server operation is in progress.


Editable yearly details include local Save and Cancel actions. Save uses the existing
single-year override endpoint; Cancel restores only that year's saved/default values
and pending resets. Other-year and assumption drafts remain untouched. Both actions
announce their result in the details and preserve the table/page scroll context.
Field labels distinguish unsaved edits and pending resets from calculated defaults.

After a successful year save, result refresh re-applies unrelated drafts without
saving them. A refresh failure clears stale results and provides a local read-only
retry; mutations stay disabled until recovery restores the drafts. Read retries never
repeat the committed year save. Historical and household details remain read-only.
