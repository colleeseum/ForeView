# INC-09: Factual Income and Tax Value Corrections

## 1. Title and Status

**Title:** Factual Income and Tax Value Corrections

**Status:** Draft for human approval

## 2. Description

This requirement allows users to correct factual income or tax values without modifying or
deleting the underlying source record.

### Problem Statement
Users sometimes encounter inaccurate assessment, filed-return, or annual factual-record values.
Currently, there is no mechanism to adjust these values while preserving the underlying value and
provenance for auditability and future reference.

### Why Direct Editing Is Unacceptable
Editing the imported assessment or returned document directly would compromise:
- Audit trail integrity
- Reproducible projections (as this would change the source of truth)
- Data consistency across different analyses
- Historical accuracy

### How Corrections Preserve Auditability and Projection Reliability
Corrections serve as explicit overrides that take precedence over source-based resolution while:
- Maintaining the underlying source and provenance
- Preserving audit trail for how facts were derived
- Ensuring projections continue to use the correct effective value
- Supporting reliable scenario modeling

## 3. Terminology

| Term | Definition |
|------|------------|
| **imported assessment** | A government-assessed tax total loaded directly from an official document |
| **filed-return document** | A T1 or similar income tax return imported by the application |
| **annual factual-record fallback** | A manually-entered or populated annual record used when better sources are unavailable |
| **factual correction** | A separate record saying "The source-based value is X, but the application should use Y for this person, tax year, and concept because of this documented reason" |
| **source-at-correction value** | The winning source-based value when the correction was created or last reviewed |
| **current underlying value** | The value that would win normal precedence now if the correction were removed |
| **effective value** | The active correction amount when one exists, otherwise the current underlying value |

## 4. Behavior

### Core Requirements

1. **Creating, editing, or removing a correction never modifies the currently retained underlying
   facts:** Source records remain unchanged as far as the application's stored facts are concerned.
   The correction revision stores a snapshot of the underlying value and provenance.

2. **A correction targets one consolidated snapshot concept for one person and tax year.** It does
   not target or modify an individual imported document row.

3. **A correction is a separate fact record** that explicitly states a different effective value
   should be used for a person, tax year, and specific concept.

4. **A correction contains the corrected value and a required human-readable reason:**
   - The reason must explain why the effective factual value differs from the source-based value
   - A non-empty reason is mandatory for all corrections

5. **A correction takes precedence over assessment, filed-return, and annual-record fallback
   values** for that exact person, tax year, and concept.

6. **The source-at-correction value remains visible:** Users can see the underlying value and
   provenance recorded when the correction was created or last reviewed.

7. **The UI clearly indicates when a value has been corrected:**
   - A neutral visual indicator shows when a value has been corrected
   - The value's display text indicates it is corrected

8. **The UI shows source-at-correction value, current underlying value, underlying source,
   correction reason, and correction date:**
   - Source-at-correction value displayed alongside effective value
   - Underlying source details
   - Explicit human-readable reason for the correction
   - Date of creation and modification times

9. **A user can edit the correction reason or corrected value.**

10. **A user can remove the correction to restore normal source precedence:**
    - Removing a correction is safe and doesn't delete anything else
    - The underlying source record snapshot remains available for audit purposes
    - A restored value will fall back to its normal precedence
    - Removal is idempotent - requesting removal of an absent correction succeeds

11. **Removing a correction never deletes the underlying source:**
    - Corrected records are not tied to the existence of source records
    - Even if an import is later deleted, corrections remain valid with their source snapshot
      preserved for audit
    - Correction history remains even if the underlying source is deleted

12. **A correction for one year or concept does not affect another year or concept:**
    - Each correction is specific and isolated
    - Changes only impact the person, year, and concept they explicitly target

13. **Zero is a valid corrected amount for supported concepts:**
    - Corrections can result in zero values if logically correct for the scenario
    - The concept's definition determines whether zero is acceptable

14. **Reimporting the same document does not delete or silently replace the correction:**
    - Reimports have no effect on existing corrections
    - Corrections persist independently of import actions
    - A reimport may change the current underlying value and trigger review-required state

15. **If reimport changes the underlying source value, the correction remains but is flagged for
    review:**
    - System flags when a correction exists for a record that has been changed
    - Correction remains active but shows "Review required" status
    - This allows user to re-evaluate if their correction is still appropriate
    - Review status is determined by calculating an underlying-source fingerprint containing:
      - Whether an underlying value exists
      - Amount, when one exists
      - Document kind
      - Jurisdiction, when available
      - Line code, when available
      - Source name or identity
      - Source version, when available
      - Document hash, when available
    - Any fingerprint difference should require review
    - A source appearing or disappearing is also a fingerprint difference
    - Creating a correction stores the current underlying fingerprint
    - Editing the corrected amount or reason does not update the stored fingerprint or clear
      review-required status
    - Confirming the correction creates a new append-only revision containing the current
      fingerprint and clears review-required status
    - The correction remains active while review is required
    - Previous fingerprints remain available through revision history

16. **Corrections are factual adjustments, not scenario-specific projection overrides:**
    - Corrections will change the consolidated snapshot values
    - They affect core facts used by projections through an agreed input contract to be specified
      in INC-10
    - Correcting taxable income or tax does not mean the application recalculates a tax return

17. **Projection scenarios consume the effective corrected value only after INC-10 defines the
    projection input contract:**
    - Projection behavior remains unchanged until INC-10's input contract is established
    - INC-09 changes consolidated factual snapshot but does not affect current projections

18. **Corrections may only be created for values that exist in the consolidated snapshot:**
    - A correction cannot be added for a concept that has no resolved value
    - Adding a missing fact should use an annual factual record or a separate manual-fact
      capability implemented in a later feature

## 5. Precedence

| Priority | Source | Notes |
|---------|--------|-------|
| 1 | Explicit factual correction | Takes precedence over all other source values |
| 2 | Assessment value | Government-assessed tax totals |
| 3 | Filed-return value | The T1 or similar tax return values |
| 4 | Supported annual factual-record fallback | Manual annual record only for concepts without assessment or return data |
| 5 | No value | Result is none/empty |

Precedence applies separately for each person, tax year, and concept. Correlations between
different tax concepts should not affect the resolution of other concepts.

## 6. User Workflow

### Correction Process for Latest Year
1. **Open the Income page** in the application
2. **View the consolidated snapshot** showing latest tax-year values
3. **Select a value** to correct by clicking "Correct" or similar action
4. **Review current underlying value and provenance** details in correction dialog
5. **Enter the corrected value and required reason** with clear description
6. **Save the correction** that becomes active immediately
7. **See the corrected effective value** in the summary view
8. **Expand source details** to compare the correction with the original display
9. **Inspect revision history** or review the correction if flagged for review:
   - Reviewing a correction requires a distinct "Confirm correction" action
   - This action stores the new underlying fingerprint and clears review-required status
   - A user may save edits to the correction amount or reason without acknowledging current source
     conditions
10. **Edit or remove** the correction as needed

### Correction Process for Historical Year
1. In the Income page, select a historical tax year using the filter
2. Click on a value to access the correction workflow
3. Follow same steps as latest-year workflow with the historical context

## 7. Presentation Requirements

1. **Corrections must not use error-red styling merely because they exist:**
   - Use standard neutral UI styles to indicate corrections
   - Differentiate from errors with appropriate visual indicators

2. **Corrected values need a neutral but visible indicator:**
   - A badge or icon should show the value has been corrected
   - This should be clear but not alarming

3. **Tooltips may provide short explanations:**
   - Hover descriptions can explain correction workflow
   - Context-sensitive help for correction process

4. **Context help should explain when correction is appropriate:**
   - Help documentation section on when and how to correct facts
   - Guidance on situations where correction is valid versus when reimport would be better

5. **The system preserves the source-at-correction snapshot and provenance for audit purposes:**
   - Complete imported records may not be retained if they have been replaced by reimport
   - Users can access the source details that were active when the correction was created or last
     reviewed

6. **The UI must not imply that the government document itself was changed:**
   - Clarify in display that it's a user override, not an official change

7. **Review-required corrections need attention styling but are distinguishable from validation
   errors:**
   - Clear visual difference from ordinary correction or error styling
   - Must not be confused with validation failures

## 8. Validation and Error Behavior

1. **Person, tax year, supported concept, decimal amount, and non-empty reason are required for
   corrections:**
   - All fields must be provided or submission fails
   - Invalid concepts are rejected

2. **The initial supported concept allowlist is:**
   - employment_income
   - oas_income
   - cpp_qpp_benefits
   - other_pension_income
   - interest_investment_income
   - total_income
   - taxable_income
   - rrsp_deduction
   - net_federal_tax
   - provincial_income_tax

3. **The implementation must maintain this as one shared application-level definition** used by
   validation, snapshot resolution, API serialization, and UI presentation.

4. **Malformed or non-finite amounts are rejected:**
   - Negative amounts are not allowed for initial supported concepts
   - Invalid decimals or ranges are rejected with clear error messages

5. **Rejection must not modify the existing correction or imported records:**
   - Validation errors should not alter current state
   - Data remains unchanged on validation failure

6. **Append-only revision lifecycle:**
   - Creating a correction creates revision 1
   - Editing the corrected amount or reason appends a new revision
   - Confirming a correction appends a new revision
   - Removing a correction appends a tombstone revision
   - Existing revisions are immutable
   - Revision numbers increase monotonically within each correction stream
   - The latest revision determines the correction's current state
   - A correction is active only when its latest revision is not a tombstone
   - Optimistic-concurrency checks compare the submitted expected revision with the latest
     revision
   - Revision history remains available after removal

7. **Concurrent edits and removals are handled with optimistic concurrency:**
   - Client submits the correction revision it edited or removed
   - Saving against a stale revision is rejected with a conflict response
   - Removing an active correction with a stale expected revision is rejected with a conflict
     response
   - The existing active correction remains unchanged
   - User must refresh, see newer state, then try again
   - Editing, confirming, and removal all use the same optimistic-concurrency revision check

8. **Removal behavior:**
   - If the latest correction revision is a tombstone, another removal request succeeds without
     creating another revision
   - If an active correction exists and the submitted expected revision is stale, removal fails
     with a conflict and creates no revision
   - If an active correction exists and the expected revision matches, removal appends a tombstone
     revision
   - The latest revision determines state. A correction is active only when the latest revision is
     not a tombstone

## 9. Audit and Provenance Requirements

The following information must remain knowable for each correction:

1. **Source-at-correction value:** The winning source-based value when the correction was created
   or last reviewed
2. **Current underlying value:** What would win normal precedence if correction were removed
3. **Correction reason:** Human-readable explanation of why change was needed
4. **Creation and last-modified times:** Date/time when correction was created or updated
5. **Underlying source provenance:** Source information that would have won when the correction was
   made
   - Document kind is always available
   - Jurisdiction is available when applicable
   - Line code is available when applicable
   - Source name or identity is always available
   - Source version is available when applicable
   - Document hash is available when applicable
6. **Whether the underlying source has changed since correction:** The system flags whether the
   underlying data changed after correction

## 10. Success Criteria

### Testable Success Criteria

1. **Original underlying source remains unchanged** after adding, editing, or removing a correction
2. **Corrected value wins only for the matching person, year, and concept**
3. **Source precedence returns to normal** after correction removal
4. **Reimport does not delete or silently replace corrections**
5. **Changed underlying source triggers review-required state**
6. **API and UI expose the correction and original provenance**
7. **Projection behavior remains unchanged** until INC-10
8. **Unit and integration tests can verify every precedence and lifecycle rule**
9. **Revision history is preserved for all corrections**
10. **Concurrent updates are handled with optimistic concurrency**

## 11. Non-Goals

### What This Requirement Does Not Cover:

1. **Editing PDF content:** This is not about changing source text in documents
2. **Correcting public tax-rule packages:** Rule set definitions are handled separately
3. **Scenario-specific what-if overrides:** These are for future projections and differ from the
   correction concept
4. **Recalculating an entire tax return:** Only individual facts being corrected
5. **Multi-user approval workflows:** Single-user workflow only
6. **Implementing INC-10 or retirement projection behavior:** Focus is on fact corrections, not the
   projection system
7. **Document deletion feature:** Handling source deletions is outside this scope

## 12. Examples

### Example 1: Correcting Total Income from Government Assessment
A user imports a federal tax assessment that incorrectly parses total income. The
source-at-correction value is $95,000, but actual income was $110,000. A correction allows the user
to override only this amount while preserving all other assessment data.

### Example 2: Correcting Investment Income While Retaining Original Source
A user imports a T1 return with investment income recorded as $450, but a bank statement shows
$725. The user can correct only the investment income value while retaining the source-at-correction
value and provenance.

### Example 3: Removing Correction and Restoring Precedence

A user applies a correction for $5,000 of interest income that was incorrectly parsed as $1,000.
They subsequently notice that the source was correct and remove the correction. The underlying
$1,000 value becomes active again based on normal precedence.

## 13. Open Questions

No open product questions remain in this draft. Human approval is still required before
implementation.
