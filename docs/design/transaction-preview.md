# Transaction import preview design (IMP-01A, #150)

Parent: [IMP-01, #112](https://github.com/colleeseum/ForeView/issues/112).
Status: proposed design for review. This document does not describe an implemented
preview API or change the existing direct-import workflow.

## Outcome and delivery boundary

Show parsed financial proposals before confirmation. Selecting filenames is not a
parsed preview. Preview and cancellation must not create accounts, batches, raw
evidence, transactions, balances, GICs, account ownership, investment holdings or reconciliation changes.

Implementation spans provider parsing, shared analysis, transaction ownership and
browser workflow. Deliver those as separate atomic children of #112, each with
its own PR. Keep existing imports operational while provider adapters migrate.
Do not expose a format as preview-capable until its full proposal can be reviewed
and confirmed without falling back to a writing parser.

## Verified current boundaries

The inventory comes from the provider registry and the implementation at the start
of #150; provider discovery remains authoritative when implementation starts.

| Path | Current behavior relevant to preview |
| --- | --- |
| `web/transaction_routes.py` | Reads file bytes, detects providers, resolves accounts, calls writing importers and recalculates balances. Some confirmation responses return from inside a connection context after earlier files have run. This is not an atomic preview boundary. |
| `services/imports/csv_import_service.py` | Selects institution CSV parsers or the generic parser, then writes a batch, raw evidence and deduplicated transactions inside its own transaction context. |
| `services/imports/document_import_account_resolver.py` | Resolves statement identity and can create an account after approval. Split read-only resolution from creation. |
| `ingestion/statement_row_writer.py` | Writes raw rows and transactions, then checks reconciled periods. Preview must use separate read-only analysis, sharing matching policy without invoking this writer. |
| Institution import services | Own transaction contexts and can store snapshots, GIC/account changes, investment holding upserts/deletions and reconciliations in addition to transactions. These effects must all appear in the proposal, including writes on duplicate-file paths. |

| Source | Formats that need explicit adapters |
| --- | --- |
| Generic CSV | Date/Amount format; existing selected account required. |
| RBC CSV | Institution-specific CSV with generic fallback when not recognized. |
| EQ | Legacy PDF fallback outside the registered importer list; preserve explicit-account behavior and detection failures. Do not silently remove it during registry work. |
| RBC | Deposit statement, TFSA statement, GIC history and RESP GIC history. Include child GICs, copied parent ownership on new children, snapshots and parent balance-includes-children changes where applicable. |
| Achieva | GIC PDF, including account/term-deposit metadata, balances and copied parent ownership on new children. |
| Manulife | RRSP statement, including snapshots and holding upserts. An already-imported file can still upsert holdings in its stored batch's account. |
| Sun Life | RRSP statement and transaction history. A new statement deletes the valuation date's existing holdings and replaces them, as well as storing its closing snapshot; an already-imported statement skips these writes. |

Questrade live synchronization is outside #112. Its presence in the institution
registry does not make it a document-preview source.

## Proposed parse, analyse and apply contracts

1. **Parse bytes without persistence.** Provider adapters accept immutable content,
   filename metadata and parsing context, never a database connection. Return frozen
   values and tuples: source identity/version, account identity, transaction rows,
   printed balances, statement periods and additional proposed effects, including
   holding additions, updates and deletions with their account/valuation-date scope,
   and child-account ownership assignments with source parent, person IDs and shares. Keep raw
   evidence and source-language text distinct from translated labels. Preserve row
   order and occurrence identity used by existing deduplication contracts.
2. **Analyse against a consistent read snapshot.** A service coordinates repositories
   that read account resolution, batches, matching transactions, snapshots and
   checkpoints. Determine exact-file duplicates, overlapping rows, new-account
   proposals and reconciled-period warnings. Maintain a cumulative in-memory state
   over that snapshot, applying every earlier file's proposed effects in selection
   order before analysing the next file. This includes account creation/metadata,
   ownership assignments, transactions and matching occurrences, batches, raw evidence, balance anchors
   and rebuilds, GICs, holdings and reconciliation/checkpoint changes. Duplicate
   matching alone is not sufficient. No repository writes.
3. **Return a proposal.** Include per-file status, proposed account, dates,
   descriptions, signed amounts, source balances and all additional effects.
   Distinguish unknown values from explicit zero. Separate printed source balances
   from recalculated balances. Block confirmation for unsupported/failed files
   rather than silently confirming only a subset of the reviewed selection.
4. **Apply only after confirmation.** Revalidate, then use the existing repository
   and financial policies to persist precisely the reviewed proposal. All writes
   belong to the confirmation coordinator's transaction. Provider parsing and
   apply helpers must not commit independently.

Authoritative money uses integer cents and Decimal; dates use canonical ISO dates.
SQL remains in repositories/migration infrastructure. Retain existing raw source
tags, parser occurrence semantics, ownership/account links and source provenance.

For a new Achieva/RBC child GIC, analysis must propose the parent ownership rows
that the current importer copies, including person IDs and exact persisted shares.
Include those assignments in the reviewed account-creation effects and confirmation
transaction. Preserve each provider's empty-owner validation and copy/replace
semantics; do not fabricate a sole owner or overwrite an existing child's ownership
when the legacy path would leave it intact. Later files must resolve the proposed
child and its ownership from cumulative state rather than create another child.

Before declaring an adapter complete, audit every repository read and mutation on
its new-file, duplicate, existing-child and error paths. Maintain an explicit mapping
from each call to its state-fingerprint dependency and proposed/apply effect or
document why it has no financial effect. The examples here are not an exhaustive
substitute for that audit. Include inherited metadata such as account type, tax
treatment, child matching keys and interest-rate changes, not just transaction rows.

For example, an RBC CSV followed by its deposit statement must analyse the statement
against the CSV's proposed transactions and resulting balances. Show the resulting
transaction count, net change, difference and reconciliation/checkpoint proposal,
not a pre-selection `no_matching_transactions` result. Reordering or removing files
invalidates the preview and recomputes the entire ordered selection. Confirmation
must execute that same effect sequence within its single transaction.

An exact-file duplicate is not automatically a no-op: Manulife can refresh holdings
and the RBC deposit duplicate path can refresh reconciliation/balances. Enumerate
those effects and their stored target account explicitly rather than hiding them
behind a duplicate count. A duplicate file with no effects remains a no-op. Read-only
analysis must model each provider's existing duplicate behavior without performing it.

Do not implement preview by calling current importers against the live database
and rolling back afterward: nested transaction contexts can commit. A database
copy is not a substitute for exposing a complete parsed proposal and write set.

## Proposed preview lifetime and binding

- A preview is valid for **15 minutes** from server issuance. Use the existing
  application signing facilities with a purpose-specific salt and version; no new
  crypto dependency or custom signature algorithm. Restart/key changes may
  invalidate outstanding previews and require analysis again.
- Bind signatures and receipts to the runtime as well as their purpose. A shared
  configured application secret must not allow a development preview to authorize
  writes in a production runtime. Keep runtime paths out of tokens and responses.
- Keep selected file bytes in browser memory. Do not upload them into a persistent
  preview store or retain them on disk across requests. Any temporary multipart
  spooling must follow the existing request lifecycle and be removed when the
  request closes; it is not preview storage. Cancellation clears the preview and file
  selection. Do not put documents, proposal contents or tokens in browser storage,
  URLs, analytics or logs.
- The server issues an authenticated token binding ordered content hashes,
  filenames used by parsing, selected account mode/ID, parser identities/versions,
  canonical proposal digest, relevant state fingerprint and expiry. It must not
  trust amounts or account choices returned unsigned by the browser.
- Fingerprint all state that can change the proposal: resolved account identity and
  relevant metadata, account-creation lookup results, shared file-hash matches,
  parent ownership rows and referenced person existence for copied ownership,
  transaction matching occurrences, balance anchors, related GICs, affected holdings
  and active checkpoints/reconciliations. For holding replacement, fingerprint the
  entire account/valuation-date set, including absence, so concurrent additions,
  edits or removals invalidate the proposal. Preserve holding keys, units, prices,
  market values, allocation and provenance in effects and parity checks. Define the exact repository read set with each provider adapter;
  reject adapters with unrepresented effects.
- For child creation, fingerprint the complete parent owner/share set, including
  absence, and relevant child identity/existence. A changed, removed or added owner
  or a concurrently created matching child requires fresh analysis and approval.
  Do not silently recopy the current ownership at apply time over the reviewed set.
- The state fingerprint binds the persisted starting snapshot. The proposal digest
  binds the ordered cumulative effects derived from it. Reanalysis at confirmation
  and under the writer lock must rebuild that same cumulative state, not independently
  analyse each file against the unchanged database.
- Parse first, then perform analysis in a consistent, short-lived read snapshot.
  Close that snapshot before returning; never hold a transaction across user review.

Confirmation resubmits the original file bytes and token. Check CSRF, signature,
version, expiry, file order/content, account selection and parser versions, then
reparse and recompute the proposal. A changed fingerprint or proposal requires a
new preview and renewed approvals. Never silently apply a revised proposal.

## Confirmation, transaction and retry behavior

- Sign the individual new-account and reconciled-period effects that require
  approval. Confirmation supplies explicit approval choices for exactly those
  signed effects; issuing a preview token does not itself grant approval. A generic
  flag cannot approve a different account or newly discovered checkpoint change.
- Validate the entire file set before writing. Acquire the repository-managed
  writer lock, re-read the relevant state, and compare the fingerprint again to
  close the analysis/write race. Account creation and copied ownership, batches, evidence, transactions,
  snapshots, GIC changes, holding upserts/deletions, balance rebuilds, checkpoint updates and the confirmation
  receipt commit together. Any failure rolls the entire confirmation back.
- Allocate a server-generated confirmation identity when previewing and bind it in
  the token. Persist a uniquely constrained receipt only when confirmation commits.
  Replays of that identity and identical reviewed content return the original
  receipt/result, without repeating writes. A conflicting payload is rejected.
  Exact-file hashes alone are not sufficient confirmation idempotency.
- Check for an already committed receipt before treating its own writes as a stale
  preview. Expiry prevents a first mutation; an authenticated retry of a committed
  confirmation can recover its receipt without applying anything again.
- On an uncertain network outcome, the browser reads confirmation status. It must
  not automatically repeat a write without the idempotency contract. After a known
  commit, retry only read-side refreshes and keep stale totals unavailable.

The receipt schema needs a new append-only migration. Existing applied migrations
and historical import rows remain unchanged. No retained preview table is required.

## API and browser behavior

Add separate preview, confirm and receipt-read endpoints when the backend contract
is ready. Keep existing CSRF enforcement. Return stable localized error codes for
expired, altered, stale, unsupported and invalid previews. Preserve original source
descriptions/language; translate UI labels and owned validation only.

The browser moves through Selected files, Analysing, Review, Confirming and Committed
states. Preserve multi-file/directory selection, order and recoverable drafts. Show
account creation and reconciled-period approvals alongside their affected effects.
During requests, prevent duplicate submission and unsafe dismissal. After commit,
update rows/summaries in place and preserve filters, scroll and focus.

Use existing dialogs, disclosure and icon components. Primary Preview/Confirm and
Cancel retain labels. English/French, registered fallback and RTL follow existing
localization contracts. Preview help must describe actual capabilities, including
formats not yet migrated, without describing direct import as preview.

## Proposed implementation batches

Create and add each implementation child to the Project before starting its code.
The first implementation batch establishes contracts and proves generic/RBC CSV
parity without exposing an incomplete preview UI.

| Batch | Independently reviewable outcome | Dependency |
| --- | --- | --- |
| Shared contracts and CSV | Immutable parsed/effect proposals, read-only account/matching/checkpoint analysis and generic/RBC CSV parity tests | Reviewed #150 design |
| EQ adapter | Pure EQ PDF proposal and existing import parity, preserving the legacy explicit-account fallback | Shared contracts |
| RBC deposit adapter | Pure deposit proposal, balance/reconciliation effects and parity | Shared contracts |
| RBC investment adapters | GIC, RESP and TFSA proposals including child accounts, copied ownership and snapshot semantics; split further if necessary | Shared contracts |
| Achieva adapter | Complete term-deposit, copied-ownership and account-metadata effects and parity | Shared contracts |
| Manulife adapter | Complete RRSP statement, snapshot and holding-upsert effects, including duplicate-file refresh parity | Shared contracts |
| Sun Life adapters | Statement/history, snapshot and valuation-date holding-replacement effects and duplicate behavior parity | Shared contracts |
| Preview/confirmation API | Signed binding, expiry, writer-lock revalidation, atomic apply/receipt and replay protection; split coordination and HTTP delivery if necessary | Migrated adapters |
| Browser review | Accessible parsed review, explicit approvals, confirmation/status recovery and in-place results | Preview/confirmation API |

Each batch includes its own relevant tests and documentation. #112 stays open until
all required formats and browser acceptance are complete. Do not close a child on
push or manually close its PR in place of a merge.

## Required evidence

- Preview/cancellation/expired/altered/stale/unsupported cases leave repository
  contents and retained evidence unchanged. Verify read-only connections cannot
  write; compare financial tables and evidence, not only transaction counts.
- Synthetic golden cases preserve existing parser detection, account resolution,
  amounts, source balances, snapshots, GIC/account metadata, copied ownership/person
  shares, investment holding
  additions/updates/deletions, duplicate occurrences and reconciliation outcomes
  for each format. Cover Manulife holding refresh on reimport and Sun Life's
  valuation-date replacement, including deletion when the parsed holding set is empty.
- Multi-file tests include duplicate content, overlapping exports, an invalid later
  file, proposed account creation and mixed reconciled-period warnings.
- Cross-format tests include RBC CSV then its deposit statement: previewed count,
  net change, difference, balance and checkpoint effects must equal confirmation's
  committed results. Cover reversed order, repeated/overlapping CSV rows, account
  creation consumed by a later file and multiple holding replacements at one date.
  Cancelling all these previews must leave holdings and all other facts unchanged.
- Inject concurrent state changes after preview and before commit. Inject failures
  at each apply stage and verify complete rollback. Replay committed confirmations
  and simulate lost responses; prove only one mutation and one receipt occur.
- Change holdings and reconciliation inputs after preview, including inserting a
  holding into a previously empty replacement scope. Require a fresh preview before
  writing. Inject a later-file failure after holding deletion and prove the entire
  selection, including earlier files and replaced holdings, rolls back.
- Cover joint-owner child creation in Achieva, RBC GIC/RESP history and RBC TFSA.
  Preview/cancel must not create owner links. Confirmed owners/shares must match
  the proposal and current import behavior; existing-child paths must preserve
  their current ownership. Change parent shares, add/remove an owner, delete a
  referenced person or concurrently create a matching child after preview and
  require a fresh preview with no partial writes. A later-file failure must roll
  back both the proposed child and copied ownership.
- With a shared configured signing secret, prove tokens and receipt identities
  cannot cross runtime boundaries. Verify temporary upload cleanup after success,
  cancellation and exceptions without retaining original files in Git or fixtures.
- Browser tests cover review/cancel, explicit approvals, stale re-preview, preserved
  files on recoverable errors, read-only recovery, narrow layouts, larger text,
  keyboard focus/Escape, English/French and synthetic RTL.
- Maintain the existing coverage floors and run applicable Makefile checks. This
  design-only batch requires document/implementation-reference review and whitespace
  checks; it does not claim any new runtime behavior or preview tests already exist.
