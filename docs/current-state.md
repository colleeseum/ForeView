# Current state

Updated: 2026-10-30

## Development focus

UX-05A (#133) provides shared contextual icon-action controls for Jinja and browser
renderers, with target-specific translated names, keyboard/hover tooltips, 44px
minimum targets and vendored Feather assets with upstream notices. The disposable
component reference demonstrates the pattern; live-workspace adoption is tracked
separately by UX-05B-G under parent #131. UX-05B (#134) now adopts that pattern for
Assets account/GIC/property row actions and accessible portfolio expansion, retaining
labelled primary actions and existing financial/save contracts. UX-05C (#135) applies
the shared Help and close controls in Transactions, preserving labelled import and
reconciliation workflows and read-only history. UX-05D (#136) adopts shared Edit,
correction Details/Review and dialog-close icons in Income while retaining explicit
correction lifecycle labels and financial contracts. UX-05E (#137) adopts shared
record/category Edit, imported-record View and record Delete icons in Expenses.
Manual and imported evidence share guarded permanent deletion and in-place recovery;
a read-only record dialog exposes import provenance outside the compact table.
UX-05F (#138) adopts shared annual-override Reset and Save As Close icons in Projection,
with field/year names and unchanged draft and calculation contracts. UX-06 (#146)
prioritizes disposable income in a compact summary with expandable yearly inputs and
calculation details, retaining drafts and all existing financial values. UX-05G (#139)
aligns shared Help/Close and rule-approval Help with the same primitives, retaining
native disclosures and explicit administration workflow labels. See `docs/design/ui-foundation.md`.

Projection rate-input correction #116 separates millionth-rate precision from
cents conversion across settings, annual overrides, drafts, clones and spending.
Malformed/non-finite rates fail with localized errors and atomic rollback; existing
saved assumptions are unchanged.

The maintainer selected A / Sage for UX-03's visual direction. UX-03A's synthetic evidence and
design brief are under `docs/design/ux-03a/`. An opt-in shared CSS foundation and native-dialog
helper are implemented with a disposable bilingual component reference under `docs/design/ux-03b/`;
usage is documented in `docs/design/ui-foundation.md`. UX-03C adopts the foundation for a wider,
collapsible shared navigation disclosure with wrapped narrow-screen groups and active-page semantics.
UX-03D adopts Sage cards, panels and readable transaction history for the financial overview,
with explicit missing/empty/error states and unchanged dashboard read-model calculations.
UX-03E adopts Sage styling and standard/compact financial tables for Assets and migrates account,
GIC and property editors to shared native dialogs, with labelled ownership shares, in-context save
feedback and focus return after table refresh. UX-03F adopts Sage transaction tables,
saved density, account filters and native import/reconciliation confirmations, retaining
existing ingestion contracts and adding explicit selection review and busy/error recovery.
The import selection review is not a parsed-data preview; the existing endpoint analyses
and imports in one operation. UX-03G adopts Sage snapshot cards and peer source groups
for Income, with native annual-record, PDF review and correction dialogs, in-modal
help, guarded pending requests and read-only recovery after committed saves.
Source precedence, fingerprints and append-only correction semantics are unchanged.
UX-03H adopts Sage expense tables and native evidence/category/import dialogs,
with retained category-management context, manual evidence editing through the existing
API, guarded sequential Hydro previews and preserved overlap/seasonal calculations.
UX-03I adopts Sage employment-projection controls, factual anchors and scrollable result
tables, with native scenario cloning, guarded separate personal/spending drafts and
read-only recovery after committed saves. Projection APIs and calculations are unchanged.
UX-03J adopts shared Sage administration panels, forms, section controls and reference
tables for Setup, Connections, public rules, application settings, About and Disclaimer.
Connection status retry remains read-only. Legal content, language persistence and hash
approval contracts are unchanged. Text-size controls are delivered separately by UX-03M (#118).
UX-03K adopts Sage full help, category navigation, search status and quick-reference
tooltips, with native modal stacking, keyboard focus return and retained contextual
destinations and per-field language fallback. Help remains read-only.
UX-03L integrates the workspace acceptance matrix, read-only cross-page invariance
checks, approved viewport dimensions, rendered contrast/control samples and
synthetic stress-value/reflow evidence. The coverage index and outstanding manual
acceptance boundaries are recorded in `docs/design/ux-03-acceptance.md`.
UX-03M adds the approved Small / Normal / Large text-size preference under
Settings > Appearance, persisted per runtime independently of language and table
density. Small preserves the original typography and is the default; Normal and
Large use 112.5% and 125% of that scale. Browser zoom and 44px minimum control
targets are retained.
UX-03N localizes public-rule jurisdiction navigation using the shared province
catalog and resolves About institution names through the existing provider
presentation contract, preserving stable codes, hashes, identities and source text.
No retirement functionality is added.

The current development focus, rather than the permanent product boundary, is factual annual income
and tax records feeding an employment and disposable-income projection. The application can retain
multiple annual records, import an individual UFile T1, CRA and Revenu Québec notices of assessment,
and a Retraite Québec Statement of Participation. Detailed normalized tax concepts are retained for
future calculations and audit.

A consolidated latest-year income and tax snapshot is implemented as an API and UI read model. It
uses the newest available tax year, resolves each concept from same-year sources, retains
provenance, and does not fill a newer year with older facts. Assessment values take priority over
filed-return values, followed by the corresponding annual factual record when available. Its role
as a projection input remains to be decided.

INC-09 factual corrections are implemented. The persistence and API foundation keeps
append-only revision history, uses optimistic concurrency for mutations, records removals as
tombstones, and applies the latest active correction to the consolidated snapshot. Corrections
retain the source that was reviewed, detect changed or missing underlying sources through a
derived fingerprint, and support confirmation without losing prior revisions. A shared concept
catalog and correction validator reject unsupported concepts, invalid years, malformed or
negative amounts, blank reasons, and invalid revision guards before persistence. The Income page
supports current and historical corrections, neutral corrected indicators, source comparison,
review confirmation, editing, removal, reactivation, and revision history.

The implemented employment projection supports factual salary anchors, raises, a first non-working
date with partial-year proration, recurring and annual salary/RRSP/other-employment-income
overrides, payroll contributions, federal and Quebec tax estimates, disposable income, saved
scenarios, scenario cloning, and coarse required/discretionary household expenses.

Factual household expenses are retained separately from scenario assumptions. Users can manage
required or discretionary categories, record dated manual evidence, associate it with the
household, a person, an account, or real estate, and review annual summaries. Potentially
overlapping evidence within the same stable expense identity must be resolved before an annual
factual total is available. Irregular recurring statement periods retain their factual amounts.
When a complete preceding year is available, a separately labelled seasonal estimate combines
current actuals with the prior-year pattern for uncovered dates using a displayed 2% inflation
assumption. A discoverable
expense-source contract supports previewed and confirmed Hydro-Québec, Énergir and Montréal municipal-tax PDF imports with
import-batch and parser provenance.
EXP-02 (#128) adds confirmed permanent deletion of imported expense evidence, including
excluded duplicates. It checks the displayed record against concurrent changes, preserves
shared provenance and explicit exclusions, and refreshes only affected overlap flags.
UX-05E (#137) extends the same deletion safeguards to manual evidence.
Deletion updates rows and summaries in place, preserving scroll, expanded groups and
unrelated notes. Manual evidence retains Edit. See `docs/design/expenses.md` for the deletion boundary.
Montréal's verified English and French two-page annual accounts import the stated calendar-year
obligation after reconciling the tax-charge lines and two installments. It does not
import payments, coupons, optional financing fees or assessed property values.
Its suggested identity retains the property location and account number for review;
the user confirms category and property association. The annual amount is not extrapolated.

A registry-backed localization foundation supports English and French Canadian message catalogs,
declared locale fallback chains, text direction, and a language preference stored with each
runtime. The shared side menu, selected server-rendered pages, and primary browser-generated
workflows use it through a shared browser catalog contract. Help uses expandable categories with
page and contextual branch selection, searchable category paths, and provider metadata. Shared browser
and server value formatters cover financial dates, money, quantities and percentages, including
expenses, public tax rules, account details and document dates, with locale-switching tests that
verify unchanged factual values.
Localization validation now includes persisted language changes across primary-page navigation,
synthetic RTL registration and browser fallback, unchanged financial read models, and logical
inline layout rules. Real Chromium acceptance now exercises English/French create/edit/import
workflows, calculated-result invariance, RTL placement, focus, Escape and mobile layout against
an isolated synthetic runtime. See `docs/localization.md` for the acceptance scope and exclusions.
Expense import has a rounded-square ? button matching the main-page Help control.
It opens the main Help on a generic topic explaining automatic PDF source detection
and listing supported vendors/municipalities from the registry.
The topic replaces separate provider entries and notes that more vendors and
cities can be requested. Closing Help
preserves the selected file queue and draft fields. Cancel and primary Preview
share the footer; Confirm replaces Preview during review, with logical RTL order.
Other import-help buttons resolve provider display translations with per-field language metadata.
Built-in tax, pension, expense and institution import instructions have French translations,
shared with full help and retained as language-tagged fields in the transaction dialog.
Explicit request validations now expose stable error codes, localized text and resolved language;
owned account, income, expense, real-estate, projection and built-in parser validations use that
contract. External and operational diagnostics retain their original wording.
Factual-correction validation and concurrency/not-found failures now expose localized error codes,
with bilingual lifecycle tests preserving revision history and underlying records.
Expense validation and source-detection failures now share localized JSON/form error handling;
bilingual workflow tests verify rejected-request immutability and retained evidence/audit notes.

Questrade status reads no longer refresh tokens. Refresh failures are isolated to the selected
login and reported with safe localized guidance while synchronization and reconnect controls
remain available. Failed refreshes preserve credentials; successful rotations are committed
independently of other logins' failures.

## Intentional or known limitations

- The broader retirement cash-flow, account drawdown, CPP/QPP and OAS benefit, RRIF/LIF,
  withdrawal-order, estate, and optimization engines are not implemented.
- Projection algorithms are not yet registered or composed by time period. The current salary
  service is a concrete implementation rather than a general projection contract.
- Salary projection still reads its factual anchor directly from annual employment records. It
  does not yet consume the consolidated T1/assessment read model.
- Employment tax projection is Quebec-oriented. Province of residence is stored, and payroll can
  use QPP or another province's CPP/EI parameters, but the projection service currently always
  applies the Quebec provincial income-tax calculator.
- Scenario comparison is not implemented even though scenarios can be saved and cloned.
- Expense tracking remains high-level rather than transaction-level budgeting. Hydro-Québec and
  the verified two-page bilingual Énergir gas-bill layout are supported. Énergir rental bundles,
  equal-payment plans, corrected bills, scans and older unverified layouts remain unsupported;
  Montréal property-tax imports support the verified English and French annual two-installment
  layouts. Partial-year/supplementary accounts, receipts and
  balance statements remain unverified. Spreadsheet expense imports are not implemented.
- Account-type providers describe classification and presentation behavior but do not yet supply
  full projection, beneficiary, contribution-room, or withdrawal contracts. RESP beneficiary
  modeling is therefore absent.
- UFile is the only T1 source. T4 import is intentionally not part of the current factual-income
  workflow. Document parsers remain format-sensitive and require user review.
- Public-rule import supports annual numeric changes but still requires human review for added,
  removed, or structurally changed government concepts.
- The application has no authentication or tenant isolation and is suitable only for a trusted
  local environment.
- Contributed provider translations may be incomplete and use explicit per-field fallback.
  External diagnostics and authoritative legal/source text retain their original language.
  Localization browser acceptance covers representative Chromium workflows, not certification of
  every browser, assistive technology or contributed locale.
- Canonical ISO date-only storage is the architectural rule, but some legacy repository write
  paths still validate without normalizing dates or retain unchecked date strings. Changed paths
  must normalize new values; repository-wide enforcement remains follow-up data-integrity work.
- The project is source-available under PolyForm Noncommercial 1.0.0. Commercial use requires a
  separate written license from Mindstep Corporation.

## Next decisions and steps

The authoritative priorities, execution order, and progress are maintained in the
[GitHub Project](https://github.com/users/colleeseum/projects/3). This document records the current
implementation state and intentional limitations without duplicating the changing roadmap.

A dependency-based organization plan for ARCH-01A (#69) is accepted and documented in
[`structure/arch-01a-plan.md`](structure/arch-01a-plan.md). Its planning delivery is complete.
ARCH-01B-1 (#76), batch 70-1, has landed: the six shared browser modules are under `static/shared/`,
with updated consumers and recursive syntax/coverage checks.
ARCH-01B-2 (#77), batch 70-2, has landed: accounts, dashboard and setup use feature directories.
ARCH-01B-3 (#78), batch 70-3, has landed: transactions and connections use feature directories.
ARCH-01B-4 (#79), batch 70-4, relocates the final five browser modules under income, projections,
expenses and help, with updated consumers and canonical-path tests.
ARCH-01C-1 (#80), batch 71-1, groups ten account, reporting and projection services under capability
packages, with canonical consumers, recursive coverage filters, executed-coverage checks and
fresh-process startup/identity tests.
ARCH-01C-2 (#81), batch 71-2, groups eleven income, import and expense services under capability
packages, with canonical provider/parser bindings, updated patch targets and extended fresh-process
checks.
ARCH-01C-3 (#82), batch 71-3, groups the remaining six transaction and runtime services, including
startup repairs and backup/restore, with canonical institution/CLI consumers and extended
fresh-process identity checks. All 27 service implementations now use capability packages, and
synthetic generators live under `devtools/synthetic/`. The maintainer approved internal path changes
without compatibility aliases; deployment requires a full browser reload.
