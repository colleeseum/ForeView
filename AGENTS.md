# Project working rules

## Test integrity

- Treat an existing failing test as evidence about application behavior. Fix production code first.
- Do not weaken, delete, rewrite, or change the expected result of a test merely to make it pass.
- If a test appears incorrect, obsolete, or inconsistent with a new requirement, explain the issue to the user before modifying the test.
- When a requirement intentionally changes, state which tests must change and why before making those test changes.
- Add a regression test when fixing a defect that was not already covered.

## Coverage

- The project target is at least 80% branch-aware coverage.
- The enforced baseline may temporarily be lower while legacy gaps are closed, but it must not be reduced to accommodate new failures.
- Raise the enforced baseline monotonically as coverage improves until it reaches 80%.
- Prioritize meaningful coverage of balances, imports, ownership, authentication, external synchronization, and projections over tests written only to increase the percentage.
