# Assets workspace

UX-03E (#99) adopts Sage styling for account categories, portfolios, GICs and real
estate. The existing backend read models, ownership arithmetic, GIC parent inclusion
rules, API routes and payload fields remain unchanged. Account balances are still
gross factual values, not projected withdrawal proceeds.

Read-only grouped tables keep explicit Add/Edit actions and account/source identifiers.
The selected category uses a filled Sage primary background, white text and a heavier
bottom border, rather than relying on a green-versus-dark text difference.
Column headers use solid Sage primary with white labels. Footer totals use a pale
Sage background, bold dark text and a strong top rule to distinguish them from both
the column headings and factual body rows.
Missing factual monetary values are labelled Unavailable rather than silently shown
as zero or left blank; the existing general-purpose money helper remains compatible.
Long labels and financial details remain available through local, labelled keyboard
scroll regions rather than ellipsized columns. Standard/Compact changes cell padding,
not font size or action targets. The last selection is saved in browser local storage
and restored on refresh or return to Assets. It is scoped to the browser origin
(including host/port), not stored in financial records or synchronized across browsers.
Invalid or unavailable storage falls back to Standard; a blocked write still allows
the current-page choice. Small/Normal/Large under Settings > Appearance independently
scales text and controls.
An empty workspace retains the active category's Add action.

The account, GIC and property editors are native modal dialogs. The shared controller
supplies modal background isolation, Tab/reverse-Tab containment and Escape handling.
The assets adapter preserves hidden-state consumers and returns focus to the matching
replacement Add/Edit button after a successful save refreshes its table, or to the
current category when the row no longer appears there. Validation failures retain
entered values and display an alert in the dialog. Successful saves publish a live
confirmation in the originating workspace. Fields retain machine-compatible input
values; display localization does not rewrite submitted dates, rates or amounts.

Successful writes are committed independently of the following read refresh. The
shared post-save callback handles read failures in the workspace instead of passing
them back to an editor's mutation-error handler. Account, GIC and property dialogs
therefore close after a successful write even when refreshed data is unavailable;
the save confirmation remains visible alongside a read-error alert and a read-only
retry action. Retry never repeats the committed POST/PUT.

While a save and its refresh are pending, all editor controls are disabled and
the Save label announces progress. Repeated submissions and Escape/Cancel dismissal
are blocked until the request settles, preventing duplicate creates and stale
requests from closing a newly opened editor. A failed write restores the controls
and retains entered values for correction or retry.

Loading/error state is separate from the underlying arrays. Category changes cannot
render stale arrays as a valid empty workspace. Add/Edit actions are rendered only
after people, accounts, holdings and property reads all succeed; recovery retries
that complete read set without changing financial records.

The account and property dirty-state guards are retained. GIC saving retains its
existing behavior rather than adding a different editing contract. Ownership controls
now label the person-selection checkbox and percentage field independently, retaining
the existing default-share adjustment and 100% property-total validation.

Dialog markup is in `_asset_dialogs.html`; the surrounding Assets template and feature
CSS opt in explicitly. Other features and modal families are not migrated implicitly.
The helper does not invent dirty-form confirmation or new destructive operations.

Node tests retain payload checks, escaping, translated values and input-state/error
expectations, with a jsdom user-agent shim for native dialog methods. Separate adapter
tests cover replacement controls, category fallback, stale close events and dismissal.
Real Chromium acceptance uses disposable synthetic runtimes to exercise account/balance,
GIC and property/ownership create/edit workflows, retained values after rejection,
unchanged numeric values on name-only edits, focus/Escape, native validation, standard /
compact tables, narrow scrolling and English/French/synthetic RTL presentation.
Delayed-write checks cover duplicate submissions and dismissal for all three editors.
Screenshots are generated under pytest's temporary evidence directory. Original
before-state evidence remains in `ux-03a/baseline/`.

Reviewed synthetic examples: [English desktop](ux-03e/evidence/en-CA-1280-assets.png),
[French mobile editor](ux-03e/evidence/fr-CA-390-account-dialog.png) and
[synthetic RTL assets](ux-03e/evidence/ar-XB-390-assets.png). The navigation is
collapsed to show feature content. Long dialogs scroll internally to keep their
fields and actions reachable; the mobile capture shows the editor's upper portion.

The GIC editor gives Parent account its own full-width row, with Reference and
Name grouped below it. The selected parent's complete identifier is repeated as
wrapping text so native select truncation does not hide it on narrow screens.
Child-row branches and rails use the Sage primary and neutral border tokens,
not the legacy orange accents.

## Contextual icon actions (UX-05B, #134)

Account/GIC and property row edits, Add subaccount and portfolio expansion use the
shared icon-action factory and delegated tooltips. Section-level Add and dialog
Save/Cancel buttons retain visible labels. Accessible names identify the account
(institution, account number and name) or property; user-entered names remain text.
Portfolio controls pair the expand/collapse icon and localized name with
`aria-expanded` and `aria-controls`. Their existing read-only toggle is unchanged.

Action groups use the shared 44px minimum target and spacing instead of separate
text-button styling. The action column is narrower; monetary and ownership columns
retain their contents. Existing data hooks, dialog guards, save payloads and
post-refresh focus restoration remain intact. Delegated tooltips support replacement
rows, keyboard focus, RTL and larger text through the common UX-05A implementation.

DOM and Chromium regressions retain factual read-model and mutation-payload checks,
verify literal source names without injected elements, and exercise shared icon
labels/targets, portfolio states and keyboard tooltips.

Assets adoption also guards a shared-tooltip Escape race: removing the popup can
synthesize pointer entry on its anchor. Dismissal now persists until a genuine
pointer/focus exit, preventing immediate reopening over the still-focused action.
