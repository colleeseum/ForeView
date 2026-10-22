# Expenses workspace

UX-03H (#102) adopts the opt-in Sage foundation for factual spending summaries,
category management, dated evidence, overlap resolution and statement imports.
No parser, schema, annual allocation, overlap or seasonal-estimation calculation
changes are included. Required/discretionary classification, association, source
identity and irregular service periods remain explicit. Estimates stay separately
labelled from actual facts, with the existing base-year, inflation and method help.

Tables retain their columns, wrapping source identifiers and overlap audit notes.
Captioned, labelled keyboard scroll regions contain wide data on narrow screens.
Add/Edit remain explicit actions; manual evidence can be edited through the existing
update API while imported evidence stays read-only. A name-only edit must preserve
the recorded amount, dates, amount basis, association and historical category snapshot.
Archived categories remain selectable only for their existing manual records; they
cannot be chosen for new records or moves from another category. Changing the category
explicitly adopts the new category's current name and classification.

## Dialog and save lifecycle

Manual evidence, category management/editing and statement review use the shared
native modal controller. A category editor returns to management on Cancel/Escape.
Successful category saves return to the same management context, with a visible
live confirmation and refreshed read-only table. The active management dialog is
rendered open after a server-requested redirect so its feedback remains accessible
without the module, then promoted with `showModal()` when enhancement is available.

Manual and category editors use the existing JSON endpoints for in-modal validation;
request field meanings, CSRF and backend validation remain unchanged. Existing form
actions remain fallback paths. Pending requests disable editing and dismissal, with
repeated submissions ignored. Failed validation retains input and shows a localized
alert in the editor. A successful mutation is followed only by a read navigation,
with a read-only link to saved records if navigation is delayed; it is not resubmitted.
If edited dates no longer intersect the selected year, that navigation follows the
resulting period's end year so the saved evidence remains visible.

Statement selection lists all filenames before sequential parsing and confirmation.
The preview shows actual parser amounts and service periods as read-only values;
the confirmation service still re-parses the uploaded bytes and does not trust
browser-displayed amount/date values. Analysis/save progress is indeterminate.
Busy guards lock the file picker, fields and dismissal controls. Invalid files can
be replaced without dropping previously saved queue progress. Dismissing an idle
partially saved queue navigates to its saved evidence instead of implying rollback.
Duplicate-source bytes still enter the existing overlap-resolution workflow.

Provider help is rendered from the existing help API inside the native modal, with
safe text nodes and per-field language metadata. Empty-category onboarding retains
the direct Create category action. The incompatible legacy backdrop module URL is
invalidated with a new versioned entry URL. No extra parser or framework is added.

## Verification

Existing DOM tests retain request and queue-replacement assertions, with native
dialog user-agent methods shimmed rather than simulating legacy backdrop dismissal.
Additional checks cover pending-submit/dismissal locks, retained category validation
input, in-modal help escaping and language metadata, invalid analysis and save recovery.
Existing parser/service/route tests remain authoritative for amounts, service-date
boundaries, source provenance, overlap status and annual estimates.

Chromium acceptance uses only disposable synthetic data in English, French and RTL
at desktop and narrow widths. It exercises category create/edit with retained context,
manual irregular-period create/edit, two-file Hydro preview/import, duplicate-source
resolution, invalid-file recovery and empty-category onboarding. Before/after reads
verify unchanged factual values, and presentation-only navigation preserves displayed
seasonal estimates. The synthetic Hydro fixture covers January 1-31 despite its
excluded opening boundary being December 31; this follows the established parser.

Before-state evidence remains under `ux-03a/baseline/`. Reviewed after-state examples:

- [English desktop](ux-03h/evidence/en-CA-1280-expenses.png)
- [French mobile](ux-03h/evidence/fr-CA-390-expenses.png)
- [Synthetic RTL](ux-03h/evidence/ar-XB-320-expenses.png)
