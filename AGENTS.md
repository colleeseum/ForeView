# Instructions for coding agents

These instructions apply to every coding agent working in this repository. The Git repository is
the shared project memory. Do not rely on access to prior agent conversations.

## Before substantial work

Read these tracked documents before substantial work:

- `README.md` for product scope, setup, runtime operations, assumptions, and safety warnings;
- `CONTRIBUTING.md` for contributor workflow, project principles, and the intended product scope;
- `docs/architecture.md` for the implemented system structure and boundaries;
- `docs/decisions.md` for durable design decisions and their rationale;
- `docs/current-state.md` for the active development focus, known limitations, and next steps;
- the [GitHub Project](https://github.com/users/colleeseum/projects/3) for roadmap priorities and
  progress;
- focused documents such as `institutions/README.md`, `docs/tax-document-concepts.md`, and
  `docs/retirement-projection-concepts.md` when the task touches those areas.

Inspect the relevant implementation and tests before proposing changes. Treat executable code and
tests as authoritative when documentation conflicts with implementation, but flag and correct the
stale documentation. Follow established project patterns unless there is a justified reason to
change them.

## Progress reporting

For substantial tasks, do not work silently for long periods.

- Break large tasks into smaller, clearly defined steps before implementation.
- Report the initial plan before beginning substantial investigation or changes.
- Provide a brief progress update after each meaningful investigation or implementation step.
- If analysis is taking longer than expected, report what has been learned, what is currently being
  investigated, and what remains.
- Do not spend more than approximately five minutes on extended analysis without providing a
  progress update when the agent interface permits it.
- Prefer incremental investigation and implementation over attempting to understand the entire
  system before making progress.
- If the requested task is too broad to execute efficiently, propose a smaller sequence of tasks
  rather than silently performing an exhaustive analysis.

## Engineering expectations

- Follow sound software-engineering practices. Prefer encapsulation, cohesive components, clear
  responsibilities, and immutable domain values where practical.
- Keep one primary class per Python module where practical. Small supporting types and module-level
  functions are acceptable when they are tightly coupled to that class.
- Keep SQL in `repositories/` or schema and migration infrastructure. Domain objects, services,
  Flask routes, institution modules, and browser code must not issue SQL directly.
- Preserve the boundaries described in `docs/architecture.md`. Flask routes adapt HTTP requests and
  responses; services coordinate workflows; repositories own persistence; domain and projection
  modules own financial meaning and calculations.
- Avoid unnecessary coupling and duplication. Reuse provider contracts and shared ingestion
  components instead of adding institution, account-type, or document-source conditionals to the
  application core.
- Preserve backward compatibility unless a requirement explicitly changes behavior. Applied
  database migrations are append-only; add a new migration rather than editing an existing one.
- Represent authoritative monetary storage as integer cents and perform financial arithmetic with
  `Decimal`. Do not introduce new binary floating-point money calculations.
- Do not introduce dependencies without a concrete justification. Prefer the standard library and
  existing project dependencies when they are sufficient.
- For APIs, libraries, security practices, and technologies where current behavior matters,
  consult current authoritative documentation when web access is available instead of relying only
  on model knowledge.
- Preserve private-data boundaries. Never commit runtime databases, imported personal documents,
  credentials, tokens, certificates, generated private backups, or extracted personal data. Use
  synthetic fixtures for tests and examples.
- Preserve the source-available licensing boundary. New first-party source files must carry the
  applicable Mindstep Corporation SPDX notices. Do not apply those notices to third-party,
  downloaded government, generated, binary, or otherwise externally owned material. Existing
  applied migrations remain immutable; new migrations should include the notices.

## Application interaction behavior

- Enhanced edit and delete actions should update the affected rows and dependent summaries in
  place. Preserve scroll position, expanded sections, filters, selection, unrelated drafts and
  keyboard focus. Do not reload or navigate the whole page merely to show a saved mutation.
- Announce success and errors in context. After a mutation commits, recovery must retry only
  read-side refreshes, never repeat the mutation. Keep stale totals unavailable until refreshed.
- Ordinary form navigation may remain as a progressive-enhancement fallback. Apply this guidance
  to new and touched workflows; track broader existing-workflow migrations as separate issues.

## Test integrity and completion

- Treat an existing failing test as evidence about application behavior. Fix production code first.
- Do not weaken, delete, rewrite, or change an expected result merely to make a test pass.
- If a test appears incorrect, obsolete, or inconsistent with a new requirement, explain the issue
  before modifying it. When a requirement intentionally changes, state which expectations change
  and why.
- Add appropriate unit tests for new behavior and a regression test for every defect not already
  covered. Add integration tests where they exercise a meaningful boundary or workflow.
- Maintain at least 80% branch-aware coverage wherever this project measures coverage. Never lower
  an enforced threshold to accommodate a change. Prioritize balances, imports, ownership,
  authentication and security boundaries, external synchronization, tax calculations, and
  projections over superficial coverage.
- Run the relevant focused tests while working. Before considering substantial work complete, run
  the applicable checks from `Makefile`; use `make qa` for a full release-level verification when
  the environment and task scope permit it.
- Commits should be coherent and reasonably atomic. Do not include unrelated user changes or
  untracked working material.

## GitHub work tracking

- A maintainer request to review a pull request includes independently verifying findings,
  fixing confirmed defects, running relevant checks, and committing and pushing the scoped
  fixes, unless the request explicitly limits the work to analysis. Merging still requires
  an explicit request. Preserve unrelated work and report any blocker before publishing.
- Start substantial feature and defect work from an issue in the authoritative GitHub Project.
- Keep implementation issues atomic: one cohesive, independently reviewable outcome with explicit
  acceptance criteria, normally delivered by one pull request. Use parent issues for broader work
  and create a sub-issue for each planned PR-sized batch before implementation. Explain exceptions
  rather than silently spreading one implementation issue across multiple PRs. Close a leaf issue
  only after its completing PR is merged; close its parent after all required children are complete.
- Whenever creating an issue, including a sub-issue, add it to the authoritative GitHub Project
  as part of the same workflow. Set an appropriate Project status and link its parent when
  applicable. Verify Project membership; report any failure instead of claiming the issue is
  fully tracked.
- Include the roadmap identifier in the branch name, for example
  `feature/inc-10-projection-input`.
- Include both the roadmap identifier and GitHub issue number in commit subjects, for example
  `INC-10 (#10): Use consolidated snapshot as projection input`.
- Reference the issue from the pull request. Use `Closes #10` only when the pull request completes
  the entire issue; use `Refs #10` for partial work.
- When pushing a task branch, create a pull request as part of the same workflow if one does not
  already exist, unless the maintainer explicitly requests otherwise. Subsequent pushes update
  the existing PR; do not create duplicates. Include the issue links, scope and verification
  results, and report the PR URL. Opening or updating a PR does not authorize merging it.
- Keep the issue and Project status aligned with the implementation. Do not rewrite established
  history solely to retrofit this convention to older branches or commits.

## Git identity

- Commits attributed to Serge Colle must use `serge.colle@mindstep.ca` for both author and
  committer identity. Do not use another address.
- Run `./scripts/configure-git-identity.sh` after cloning or recreating the repository metadata.
  It pins the identity in the repository-local Git configuration and enables `user.useConfigOnly`.
- Install both local gates with
  `.venv/bin/pre-commit install --hook-type pre-commit --hook-type pre-push` after installing the
  development dependencies.
- Run `make identity-check` before committing. Do not bypass the identity check or its CI result.
- Do not use GitHub's merge, squash, or rebase buttons. After review and successful checks, land
  the accepted commit from a correctly configured local checkout and push it to `main`. GitHub can
  otherwise source committer identity from account profile metadata instead of local Git config.
- For a local squash landing, keep the PR open and align its task branch with the accepted
  locally created squash commit, using an explicit force-with-lease against the verified old
  branch head. Push that same commit to `main`, then verify GitHub reports the PR as `MERGED`.
  Do not substitute manually closing the PR for merged tracking. Never rewrite `main` for this.

## Maintaining shared project context

Keep the shared project documentation current as work proceeds. When a change alters architecture,
a durable decision, an important assumption or constraint, implementation status, or a significant
next step, update the appropriate shared document before completing the task. Do not wait for an
explicit documentation request. Replace or remove stale statements rather than adding
contradictory notes.

Record only durable project knowledge. Do not add routine implementation details, transient
debugging history, conversation transcripts, facts easily discovered from code, or speculative
decisions that have not been made. Do not duplicate material that has a more appropriate focused
home elsewhere in the repository.
