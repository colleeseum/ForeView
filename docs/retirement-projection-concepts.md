# Retirement projection concepts

Status: requirements notes for later projection work. This document does not
define calculation formulas or authoritative example values.

## Annual cash-flow schedule

The projection should provide an annual schedule over the planning horizon. A
row represents one projection year and includes the applicable age for each
person. Household totals may be displayed, but income, tax, eligibility, and
account activity must remain traceable to the person who owns them.

Keep materially different inflow sources separate:

- employment income;
- CPP or QPP benefits;
- OAS benefits;
- defined-benefit pension income;
- RRSP or RRIF withdrawals;
- LIF or LRIF withdrawals;
- private-corporation dividends;
- rental and other income;
- TFSA withdrawals; and
- non-registered account withdrawals.

The list should be extensible. These categories describe the concepts visible
in the reference example, not a closed schema.

## Derived annual results

For each year, show or make available:

- total inflows, derived from the individual inflow sources;
- total spending and other outflows;
- estimated taxes;
- annual surplus or funding deficit; and
- closing balances after income, withdrawals, contributions, growth, taxes,
  and spending have been applied.

The calculation contract must state whether taxes are included in total
outflows. They must never be deducted twice. A surplus or deficit should be a
derived result, not an independently entered amount.

## Modeling implications

Account distributions are funding decisions, not interchangeable income. An
annual withdrawal strategy must choose the source account and preserve its
effects on taxation, registered-account restrictions, contribution room, and
the account's remaining balance.

Benefit and pension streams need their own start dates and applicable rules.
Examples include CPP or QPP election age, OAS eligibility, pension indexing,
bridge benefits, reductions, and survivor treatment. Those rules belong in
calculation services and versioned public-rule data, not in this presentation
schema.

The schedule must support dated or one-time events that can make one year very
different from adjacent years, such as an asset sale, major purchase, debt
repayment, inheritance, or exceptional distribution. Every exceptional amount
should be explainable from its source event rather than appearing only as a
large annual total.

Every projected amount should retain provenance to the relevant assumption,
public rule, event, benefit, expense, or source account. This is required so a
user can understand why a value changed and compare scenarios.

## Reference boundary

The supplied table is a conceptual reference for the annual schedule. Its
numbers, dates, ages, highlighted year, ordering, and exact labels are not
inputs, expected outputs, or test fixtures.

## Scenario and outcome reference

A second reference illustrates several concepts that may complement the annual
cash-flow schedule:

- a stacked annual net-worth projection, separated into lifestyle assets,
  registered accounts, TFSAs, non-registered accounts, and liabilities;
- a total net-worth series overlaid on the asset composition;
- a retirement-goal result expressed as a probability or confidence measure;
- a distinct projected legacy or terminal-estate result;
- alternate views for cash flow, taxes, income, detailed income, goal progress,
  and the ability to fund individual goals; and
- optional planning actions or scenario levers whose effect can be compared
  with the baseline.

These outputs require explicit definitions before implementation. In
particular, a retirement success percentage is meaningless without its
simulation method, time horizon, success condition, market assumptions, and
treatment of inflation and taxes. A legacy value similarly needs a defined
valuation date, estate costs, taxes, liabilities, and ownership treatment.

Scenario actions should modify named assumptions or events and produce a
reproducible comparison against a saved baseline. Any displayed improvement or
decline should identify the metric affected and the assumptions responsible for
the change. Examples may include spending changes, TFSA funding choices,
taxable-income management, or investment-allocation changes, but these are not
yet adopted product recommendations.

The stacked projection is a useful diagnostic because it shows not only total
wealth but also which asset pools fund later years and when each pool is
depleted. Category totals must reconcile with the underlying projected account
balances. Liabilities and negative terminal values must remain visible rather
than being truncated at zero.

As with the annual schedule reference, the supplied interface, labels, values,
recommendations, and visual design are reference material only.
