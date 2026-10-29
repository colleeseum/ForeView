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

UX-04 (#127) provides one **?** button immediately after the import title,
using the same rounded-square shape and styling tokens as the main-page Help
control. Its localized accessible label and tooltip identify import help, and
its target remains at least 44px. It uses the existing contextual-help handler
to open the main Help on **Import expense statements**, including before category
setup. This generic topic explains automatic vendor/municipality detection from
the PDF, preview and confirmation, rejection of unsupported PDFs, and lists the
registered sources. The registry supplies that list automatically. There is no
separate in-dialog directory or extra help navigation. Closing main Help restores
focus to the title button without changing the file queue or draft values.
Expense imports has only this one topic, without separate provider entries. It
also notes that support for additional vendors and cities can be requested.
The source list is appended independently of translated prose, after per-field
fallback resolves the body and its language. Partial title/summary translations
therefore remain usable even when a body falls back. Main Help shares pending and
successful catalog requests, but discards failed requests so reopening can retry
after network, HTTP, JSON or catalog-shape failures without reloading the page.

The footer groups Cancel before the primary Preview action in logical reading
order. On successful analysis, Confirm replaces Preview in the same position;
analysis errors restore Preview. Busy guards and queue behavior are unchanged.
The shared footer wraps on narrow screens and follows RTL direction.

Regression checks cover main-Help stacking and focus return in
English, French and synthetic RTL, preserved files and draft values, matching
main-page/title-help shapes, primary-action placement and category setup. Route
tests verify that expense imports has exactly one generic article, listing the
registered sources and the request-support note in each supported locale.
Narrow-screen selection/review screenshots were inspected.

EXP-01C (#43) adds the verified English and French Montréal annual municipal-tax accounts
through the same preview and confirmation workflow. The printed account total is
an annual billed obligation over its stated January-December taxation period,
not a payment. Charge lines and two scheduled installments must reconcile to it.
Coupons, optional payment-plan interest and taxable property values are excluded.
The suggested identity includes the property address and account number; the user
confirms its category and property association. Use a consistent identity and
association when recording related manual installments so overlap review can
exclude duplicate evidence. Identical document reimports also require review.
The synthetic fixtures are `fixtures/montreal-municipal-tax.pdf` and
`fixtures/montreal-municipal-tax-fr.pdf` in new synthetic runtimes. The suggested
identity is independent of source/interface language; importing both language
copies for the same identity/category/association requires overlap review.
The private sources and personal details are not repository fixtures.
See [provider guidance](../../expense_sources/montreal_tax/HELP.md) for format limits
and official sources distinguishing the original annual account from later payments.

EXP-01C verification on 2026-10-28 passed full `make qa`: 762 Python tests,
176 integration tests and 112 JavaScript tests, with 91.86% overall branch-aware
Python coverage and unchanged thresholds. Chromium acceptance imports both source
languages through English, French and synthetic RTL interfaces, verifies preview
immutability and the selected property, and requires overlap review for language
copies of the same obligation. Agent verification parsed both private bills
read-only without importing private financial data into a runtime.
The maintainer reported functional manual testing passed on 2026-10-28.
Separate follow-ups cover import help/action layout (UX-04, #127) and permanent
deletion of accidentally imported expense evidence (EXP-02, #128).

EXP-01B (#42) adds the verified two-page bilingual Énergir PDF layout through the
same provider-neutral preview/confirm workflow. It reads the current gas-period
charge including taxes, not payment balances or total due. Header, charge and
detail dates must agree with the inclusive printed day count. The subtotal and
both taxes must reconcile to one unambiguous total; duplicate printed columns
must agree. Unsupported rental bundles, equal-payment plans, corrected bills,
scans and unverified layouts are rejected. See the provider's
[import guidance](../../expense_sources/energir/HELP.md) for supported formats.

The supplied private PDF was inspected and parsed outside the repository. Only
invented identities, dates, amounts and document bytes appear in committed tests
and fixtures. The fixture generator produces `fixtures/energir-gas-bill.pdf` in new
synthetic runtimes, and browser acceptance imports it in English/French/synthetic RTL.
Preview provider labels use the shared resolver and resolved-language metadata;
the provider's stable key and persisted provenance remain unchanged.

For EXP-01B on 2026-10-27, full `make qa` passed: 686 Python tests, 171
integration tests and 112 JavaScript tests, plus formatting, type, identity,
license, security and dependency checks. Overall Python branch-aware coverage
was 91.7%, with no reduced thresholds. The private source PDF and extracted
personal details are not test fixtures or repository artifacts.

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
