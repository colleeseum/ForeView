# Financial overview presentation

UX-03D (#98) adopts the Sage foundation for the existing dashboard. The HTTP read
model, ownership aggregation, monetary arithmetic and stored records are unchanged.

The landing page still reports gross assets, real-estate estimates, securities,
GICs, preferred/available liquidity and two existing review cues linked to Assets.
Registered balances remain pre-withdrawal-tax values; RRSP cash remains separate
from available liquidity. No net-worth subtraction, retirement funding, lifetime
tax, estate, forecast, chart API or synthetic action count is introduced.

Metric cards use responsive tracks, readable shared typography and tabular
figures. Warning-colored review links are not assertions of a financial loss.
Category, liquidity and maturity panels remain factual read models. Real-estate
values remain estimates, explicitly labelled. Transaction history retains source
language evidence, captioned headers and a labelled keyboard-scroll region.
Existing locale-aware money, date and number helpers remain authoritative for
display; monetary compatibility precision guards are retained.

Explicit numeric zero is displayed as zero. A missing/null monetary field is
displayed as Unavailable, never silently changed into zero. Empty category,
maturity and transaction lists have explicit empty messages. Initial loading has
a status indicator and busy semantics. After a failed HTTP request, network
failure, malformed response or unsafe amount, one error alert replaces the
metrics and all dependent panels become unavailable, with busy flags cleared.
This avoids leaving stale Loading text or apparently valid partial results.

`static/dashboard/dashboard.css` scopes feature styling beneath `fv-dashboard`
and uses the shared semantic tokens rather than duplicating theme constants.
The shared navigation remains independently collapsible. Text-size selection
is still deferred to UX-03J; the current showcase scale is not a final size policy.

Node regression tests cover English/French, source escaping/language, monetary
precision, explicit zero versus missing facts and all-panel failure states.
Real Chromium tests reuse disposable synthetic runtimes in English, French and
synthetic RTL at 1280/390/320px. They verify card fit, dashboard overflow, unchanged
API values, loading/error transitions and missing/empty states. Synthetic screenshots
are generated in pytest's temporary evidence directory; original baseline evidence
is retained in `ux-03a/baseline/`.

Reviewed synthetic examples: [English desktop](ux-03d/evidence/en-CA-1280-dashboard.png)
and [French mobile](ux-03d/evidence/fr-CA-390-dashboard.png). The navigation is
collapsed in these captures to show the dashboard content, not to imply a change
to the shell's default expansion policy.
