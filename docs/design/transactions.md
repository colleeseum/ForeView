# Transactions workspace

UX-03F (#100) adopts the Sage foundation for transaction categories, account filters,
tables, import history and import/reconciliation dialogs. Routes, request field names,
CSRF protection, financial calculations and database schemas remain unchanged.

Category buttons expose their pressed state and use the same filled selected style
as Assets. Standard/Compact changes table padding, not font size, chronological order,
account selection or monetary values. The choice is saved in browser-origin local
storage under a Transactions-specific key, independently of Assets and text size.
Wide tables use labelled, keyboard-focusable scroll regions. Headers use the Sage
primary background; opening-balance rows remain separately identified, not transactions.
Missing balances retain the existing blank-cell semantics rather than becoming zero.

## Import and reconciliation lifecycle

The native modal dialogs use the shared controller for focus return, Escape and Tab
containment. Users can review the complete file selection, including directory paths,
before submitting. Provider instructions remain available inside the import dialog;
full contextual help is also reachable from the workspace. Inline instructions avoid
opening the legacy help drawer behind a native modal's inert background.

The selection review is not a parsed-transaction preview; that separately approved
follow-up is [IMP-01 (#112)](https://github.com/colleeseum/ForeView/issues/112).
The existing import endpoint
analyses and writes files in one operation; this UI does not invent a dry-run API or
promise atomic rollback across all selected files. Server requests for account creation
or reconciled-period confirmation use a second native modal, defaulting focus to Cancel.
Cancellation retains files and account selection. If earlier files were already processed,
the cancellation message says so and refreshes the table/history.

During a mutation, fields and dismissal buttons are disabled, Escape cannot close the
originating dialog, and repeated submissions cannot create concurrent requests. Busy
feedback is indeterminate: there is no server-provided per-file progress percentage.
Validation/network failures retain user inputs and expose an alert. Successful writes
close the dialog, restore focus and publish persistent feedback with duplicate counts.
A subsequent refresh failure is reported separately, not as a failed import/reconciliation.
Read failures have a retry action, and current-request guards prevent stale table/history
and reconciliation responses from replacing newer context.
Editors remain locked until their post-write refresh settles, so a completed older
operation cannot close a newly opened editor. Failed account, transaction and history
reads clear the affected stale rows; reconciliation-status failures are surfaced rather
than silently hiding the lock state. Mixed-file batches can request account-creation
and reconciled-period permission in either order, granting each permission at most once
per submission.

## Verification

Node tests preserve existing escaping, date ordering, account/reconciliation and import
request expectations, with additional native-confirmation, busy-submit and recovery tests.
Chromium uses disposable synthetic runtimes for English, French and synthetic RTL at
desktop and narrow widths. It checks density and sort invariance, filters, multi-file
imports, duplicate reimports, cancellation and acceptance of a reconciled-period guard,
invalid-file recovery, focus return, keyboard scrolling and visible focus. Existing
route/integration tests continue to exercise transactional ingestion and CSRF boundaries.

Before-state evidence is under `ux-03a/baseline/`, including
`en-CA-desktop-transactions.png`. Browser tests generate after-state screenshots under
their temporary evidence directory. No private statements or runtime databases are used.

Checked examples: [English desktop](ux-03f/evidence/en-CA-1280-transactions.png),
[French mobile](ux-03f/evidence/fr-CA-390-transactions.png) and
[synthetic RTL narrow layout](ux-03f/evidence/ar-XB-320-transactions.png).
