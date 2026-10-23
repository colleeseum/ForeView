# Administration and reference pages

UX-03J (#104) adopts Sage for Setup/people, Connections, public rules, application
settings, About and Disclaimer. The planned Small / Normal / Large text-size setting
is separate work in UX-03M (#118); its final scale and default are not approved here.

## Presentation boundary

All six pages opt in through the shared administration head partial and `fv-admin`.
The presentation adapter applies shared control classes, captions and labelled keyboard
scroll regions to reference tables. It also observes newly rendered controls from the
existing feature modules. It makes no network requests and does not own form submission,
financial values, connection credentials, synchronization, preference persistence or
approval hashes. The scoped stylesheet preserves hidden/inactive sections and contains
long source identifiers, hashes, table data and actions on narrow screens.

Setup uses ordinary pressed-state buttons for its sections. Public-rule jurisdiction
navigation uses links with `aria-current="page"`, not an incomplete in-page tab widget.
Rule values remain read-only, source links remain available, and explicit approval forms
still submit the exact server-rendered hash through the existing CSRF-protected endpoint.
Unavailable connection providers have a Retry status action which repeats only discovery
and status reads. It never refreshes credentials or synchronizes financial data.

Application language selection retains its existing POST/redirect persistence contract.
About retains the copyright, PolyForm license, commercial contact and full-disclaimer
link. Disclaimer text still comes from the authoritative `DISCLAIMER.md` and retains
its English language and LTR metadata even in French or RTL interfaces. No legal text,
acceptance dialog, new legal document, schema or dependency is introduced.

## Verification

DOM tests cover idempotent presentation enhancement, dynamic controls, named scroll
regions, unchanged reference values and status retries without mutation requests.
Existing Setup/Connections and route tests retain their financial, credential-isolation,
CSRF and exact-hash expectations.

Chromium acceptance uses disposable synthetic data in English, French and synthetic RTL.
It edits/restores a person's birth date, exercises all Setup sections, verifies language
save/navigation, isolates an unavailable provider, tests sync failure/recovery controls,
retries status without another POST, approves an exact public-rule hash, opens official
sources and checks legal information. Synthetic provider routes never contact real
institutions. Before/after reads verify unchanged financial data after restored edits.
All six pages have desktop/mobile screenshots, local overflow and keyboard-focus checks.

Before-state screenshots are under `ux-03a/baseline/`; after-state evidence is under
`ux-03j/evidence/`.
