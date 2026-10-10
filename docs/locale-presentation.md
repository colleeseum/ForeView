# Locale-aware value presentation (UX-02E initial contract)

Use `static/locale-format.mjs` at browser presentation boundaries. Its helpers use
the selected locale from `i18n.mjs`, or an explicit locale for tests and special cases.

- `formatDate(isoDate)`: calendar-only ISO `YYYY-MM-DD` input; UTC formatting prevents
  day shifts across browser time zones. Do not use for timestamps without specifying
  their timezone and semantic meaning. Locale or calendar-specific output is presentation
  only; persisted date values remain canonical ISO/Gregorian dates. Callers may use
  `dateStyle` or date-component options, but time-of-day options are rejected.
- `formatNumber(number)`: finite presentation numbers only; never parse the output
  back into financial calculations.
- `calendarDateSortKey(canonicalDate)`: chronological key for canonical API dates;
  malformed legacy evidence sorts before valid dates, matching the server's policy.
- `formatMoneyCents(integerCents)`: integer Canadian cents (or bigint), formatted as CAD.
  Other currency codes are rejected because the current domain model does not attach a
  currency to each monetary value. Multi-currency presentation requires an explicit
  domain contract rather than a formatter-only option.
  Only non-rounding presentation options for grouping, currency display, accounting
  signs, numbering system, and locale matching are accepted. Domain calculations
  and authoritative monetary values remain unchanged.
- `formatPercent(ratio)`: ratio inputs (e.g., 0.125 for 12.5%), not percent points.
  Callers may customize presentation and rounding options, but cannot replace the
  percentage style or hide negative signs. `signDisplay` is therefore limited to `auto`
  and `always`. The default maximum of two fraction digits applies only when the caller
  does not provide explicit precision or increment controls.
- `pluralCategory(count)`: `Intl.PluralRules` cardinal/ordinal categories.
- `plural(count, forms)`: select a locale category with required `other` fallback;
  interpolate formatted `{count}`. Languages may define `zero`, `one`, `two`,
  `few`, `many`, and `other`. Do not assume English singular/plural behavior.

Do not reformat raw imported evidence, source statement values, or provider text when
its original representation is part of provenance. Helpers are offline, browser-native,
and do not call external services.

Initial localized formatting is limited to the dashboard. Other pages can migrate in later,
reviewable slices. Account summaries, balance rebuilding, reconciliation periods, and
transaction history compare supported legacy ISO date forms by calendar date. Valid dates
returned by account summaries (including GIC start and maturity dates) and transaction history
(including opening rows) are canonical;
malformed legacy evidence is preserved and sorts before valid dates. Newly entered account,
balance, GIC, and reconciliation dates are normalized before storage. These compatibility reads
do not rewrite stored imported evidence or require a database migration.
On the same calendar date, balance snapshots retain insertion order and precede transactions.
Thus a later snapshot supersedes an earlier snapshot even when their stored ISO forms differ,
while a same-day transaction balance retains precedence over snapshots.

The dashboard's compatibility API still transports dollar floats. Its adapter recovers cents
only for finite amounts with absolute value below `2**44` dollars, where float representation
error remains below half a cent. Larger or invalid values cause a localized error before any
financial panel is rendered, rather than presenting changed cents. Exact integer-cent transport
through the dashboard query and aggregation pipeline remains follow-up work; the formatter
itself accepts arbitrary-size integer cents without this compatibility limitation.
