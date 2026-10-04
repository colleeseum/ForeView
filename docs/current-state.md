# Current state

Updated: 2026-10-03

## Development focus

The active product slice is factual annual income and tax records feeding an employment and
disposable-income projection. The application can retain multiple annual records, import an
individual UFile T1, CRA and Revenu Québec notices of assessment, and a Retraite Québec Statement
of Participation. Detailed normalized tax concepts are retained for future calculations and audit.

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
- Household expenses are annual required and discretionary totals with growth assumptions, not a
  detailed budget or transaction-derived expense model.
- Account-type providers describe classification and presentation behavior but do not yet supply
  full projection, beneficiary, contribution-room, or withdrawal contracts. RESP beneficiary
  modeling is therefore absent.
- UFile is the only T1 source. T4 import is intentionally not part of the current factual-income
  workflow. Document parsers remain format-sensitive and require user review.
- Public-rule import supports annual numeric changes but still requires human review for added,
  removed, or structurally changed government concepts.
- The application has no authentication or tenant isolation and is suitable only for a trusted
  local environment.
- No project license has been selected.

## Next decisions and steps

The authoritative priorities, execution order, and progress are maintained in the
[GitHub Project](https://github.com/users/colleeseum/projects/3). This document records the current
implementation state and intentional limitations without duplicating the changing roadmap.
