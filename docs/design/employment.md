# Employment projection workspace

UX-03I (#103) adopts Sage styles for the existing employment and disposable-income
projection. It does not implement a retirement engine, scenario comparison, real/nominal
conversion or a different factual anchor. The API, Decimal calculations, rule approvals,
retirement-date proration, schema and saved-scenario payload contracts are unchanged.

## Presentation and interaction

Factual salary-anchor outputs remain read-only and link to Income. Scenario assumptions,
historical actuals and calculated estimates retain separate sections. Annual overrides
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
