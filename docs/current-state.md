# Current state

Updated: 2026-09-29

## Development focus

The active product slice is factual annual income and tax records feeding an employment and
disposable-income projection. The application can retain multiple annual records, import an
individual UFile T1, CRA and Revenu Québec notices of assessment, and a Retraite Québec Statement
of Participation. Detailed normalized tax concepts are retained for future calculations and audit.

A consolidated latest-year income and tax snapshot is currently being implemented. Its intended
resolution is to use the newest available tax year, prefer an authority's determined value over a
filed-return value for the same concept and year, retain provenance, and avoid filling a newer year
with older facts. This read model is not yet a settled projection input and should be completed and
verified before other projection features depend on it.

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

1. Finish and test the consolidated income/tax snapshot, including source-detail presentation and
   explicit rules for manual corrections.
2. Decide which resolved factual values form the projection baseline, then connect the salary
   projection through that contract without losing bonus and contribution semantics.
3. Complete meaningful salary-projection validation against factual tax records and document the
   supported provincial scope.
4. Add side-by-side comparison for saved scenarios.
5. Define a projection-algorithm contract and timeline composition before adding retirement,
   benefit, and withdrawal-strategy algorithms.
6. Expand account-type contracts only when a concrete projection or beneficiary requirement needs
   behavior beyond current metadata.

