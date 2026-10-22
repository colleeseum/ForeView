# Income workspace

UX-03G (#101) adopts Sage presentation for the existing factual Income workspace.
The consolidated snapshot stays first. Annual records, filed returns, assessments,
registered room, public pension evidence and normalized values remain peer source
groups under expandable details; T1 is not elevated above other evidence.
Annual history and its Edit actions remain separate from supplementary values.

Person selection uses labelled pressed buttons rather than claiming an incomplete
ARIA tablist interaction. Tables use captions, column headers and labelled keyboard
scroll regions; long source identifiers are retained. Corrected and review-required
cards use explicit words, not color alone. Other workspaces are not restyled.

## Dialog and request lifecycle

Annual-record editing, PDF analysis/review and correction editing use the shared
native modal controller. IDs remain stable for existing consumers. The Income
adapter coordinates hidden state, preserves each control's original disabled state
and restores focus to refreshed year/concept actions or a stable Add fallback.
Escape and visible Cancel dismiss idle dialogs. Pending requests temporarily disable
fields and dismissal; repeated submissions are ignored. Busy and error messages
are inside the active modal. Help is rendered from the existing help API inside
the modal, retaining per-field language metadata and escaped source text rather
than opening a legacy drawer behind the inert native top layer.

PDF analysis requires a file and does not persist facts. Taxpayer identity remains
visible in the annual-record preview or the assessment/pension review message.
Saving requires explicit confirmation. Rejected writes retain user input and permit
retry. A successful write is not reported as a failed mutation if the subsequent
read fails: the editor closes, save feedback remains and a separate read-only retry
reloads the workspace without repeating the write. Loads clear stale source sections,
disable mutation entry points until facts are available and ignore obsolete responses.

Correction history loads before enabling a create/reactivate save, preserving the
latest tombstone revision guard. A history failure can be retried by closing and
reopening the dialog. Creation, edit, source confirmation, removal and reactivation
retain existing endpoints, request fields and append-only revisions. Source precedence,
source fingerprints, stored monetary values and financial calculations are unchanged.
Historical-year selection and the full annual history remain available.

The template entry module and its changed corrections import use matching release
query keys. Native markup must not be deployed with legacy cached modules that only
toggle `hidden`; update both URLs when their dialog lifecycle changes together.

## Verification and evidence

Existing DOM tests retain payload, precedence, provenance and revision assertions.
Additional tests cover busy guards, retained validation input, original disabled
state, read-only recovery after committed writes, native focus return and inline help.
Real Chromium acceptance uses disposable synthetic runtimes in English, French and
synthetic RTL at 1280/390/320px. It checks source-group reachability, annual Edit,
contained scrolling, focus/Tab/Escape, unchanged facts after presentation and preview,
explicit PDF import, and correction create, underlying-source change, review confirmation,
removal, reactivation, revision history and historical-year navigation.

Before-state evidence is under `ux-03a/baseline/`. Generated after-state evidence is
captured by pytest in its temporary directory, with reviewed examples below. No private
financial documents or databases are used.

- [English desktop](ux-03g/evidence/en-CA-1280-income.png)
- [French mobile](ux-03g/evidence/fr-CA-390-income.png)
- [Synthetic RTL correction review](ux-03g/evidence/ar-XB-income-review.png)
