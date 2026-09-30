# Product roadmap and progress checklist

Updated: 2026-09-30

This is the durable progress checklist for planned product work. Change `[ ]` to `[x]` only when
the acceptance condition is implemented and verified. Add a short note when an item is deliberately
deferred or removed. Detailed architecture and rationale belong in `architecture.md` and
`decisions.md`; transient implementation tasks do not belong here.

## Current phase: factual income and employment projection

| Done | ID | Outcome | Completion condition |
|---|---|---|---|
| [x] | INC-01 | Retain annual factual income history | Multiple tax years remain available per person and the newest record does not replace older years. |
| [x] | INC-02 | Import supported factual documents | Individual UFile T1, CRA and Revenu Québec assessments, and Retraite Québec participation statements load through provider contracts with preview and provenance. |
| [x] | INC-03 | Consolidate annual income and tax facts | The latest available tax year is summarized by concept, assessment values take precedence over filed-return values, annual factual records provide supported fallbacks, and older years are not borrowed. |
| [x] | INC-04 | Preserve source details | Annual records, returns, assessments, registered-plan room, pension statements, and normalized concepts remain inspectable beneath the summary. |
| [x] | INC-05 | Project employment income | Salary growth, annual overrides, other employment income, retirement-date proration, and non-working years are represented explicitly. |
| [x] | INC-06 | Project payroll, tax, and disposable income | CPP/QPP, EI, QPIP, federal tax, Quebec tax, RRSP cash contribution, RRSP deduction, net-after-tax income, and disposable income are shown separately. |
| [x] | INC-07 | Save alternative salary scenarios | Scenarios can be saved and cloned; annual overrides can be saved, discarded, and reset to their calculated values. |
| [x] | INC-08 | Include coarse household expenses | Required and discretionary annual spending assumptions feed the projection without pretending to be a detailed budget. |
| [ ] | INC-09 | Define factual correction behavior | Decide whether an imported value can be corrected without altering its source record, and retain both provenance and the correction rationale. |
| [ ] | INC-10 | Use the consolidated snapshot as projection input | Define the exact baseline contract, including salary, bonus, other income, RRSP contribution, RRSP deduction, residence, and payroll semantics. |
| [ ] | INC-11 | Validate projection against factual results | Compare supported calculations with real factual tax records, document tolerances and unsupported cases, and add synthetic regression fixtures. |
| [ ] | INC-12 | Support Ontario employment tax | The employment projection selects a supported provincial calculator by residence and has Quebec and Ontario validation coverage. |
| [ ] | INC-13 | Compare saved scenarios side by side | Users can compare annual assumptions, income, deductions, tax, expenses, and disposable income without overwriting either scenario. |

## Next phase: projection composition

| Done | ID | Outcome | Completion condition |
|---|---|---|---|
| [ ] | PRJ-01 | Define a projection algorithm contract | An algorithm accepts factual inputs, assumptions, public rules, and a year range and returns explainable annual results. |
| [ ] | PRJ-02 | Compose algorithms over a timeline | A scenario can use one algorithm until a transition date and another afterward, such as salary followed by retirement. |
| [ ] | PRJ-03 | Support multiple employment or income periods | Multiple employers or employment periods can be represented without double-counting bonus or other employment income. |
| [ ] | PRJ-04 | Complete account-type projection contracts | Account types can supply the contribution, withdrawal, beneficiary, room, and tax behavior required by projections; RESP behavior is included when its planning use is defined. |

## Later retirement phases

| Done | ID | Outcome | Completion condition |
|---|---|---|---|
| [ ] | RET-01 | Project CPP/QPP and OAS benefits | Eligibility, start age, residence history, source statements, and rule provenance are explicit. |
| [ ] | RET-02 | Project registered and non-registered accounts | Contributions, growth, withdrawals, tax characteristics, ownership, and account conversions are represented without double-counting. |
| [ ] | RET-03 | Project retirement spending phases | Required, discretionary, known lump-sum, and expected irregular spending can vary over time. |
| [ ] | RET-04 | Produce a household cash-flow schedule | Person-level income, account flows, tax, spending, surplus, and deficit roll up without losing ownership or provenance. |
| [ ] | RET-05 | Compare withdrawal strategies | Traditional and RRSP/RRIF-meltdown strategies can be compared using the same factual baseline and explicit assumptions. |
| [ ] | RET-06 | Add deterministic uncertainty analysis | Fixed-return and historical-replay results identify their method, inputs, and run date. |
| [ ] | RET-07 | Consider optimization only after validation | Benefit-age or tax-strategy recommendations remain separate from factual and deterministic projections and expose their objective and trade-offs. |

## Ongoing quality and operations

| Done | ID | Outcome | Completion condition |
|---|---|---|---|
| [x] | OPS-01 | Separate private and synthetic runtimes | Development uses synthetic data; production data, documents, credentials, and backups remain outside Git. |
| [x] | OPS-02 | Enforce automated quality gates | `make qa` checks formatting, lint, JavaScript and Python tests and coverage, type safety, security, dependencies, and integration coverage. |
| [ ] | OPS-03 | Select and add a project license | The repository includes an explicit license suitable for the intended sharing model. |
| [ ] | OPS-04 | Define authentication scope before network exposure | Any move beyond trusted localhost use has an explicit authentication, authorization, and threat model. |
