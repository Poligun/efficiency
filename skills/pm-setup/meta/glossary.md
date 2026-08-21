# Glossary

- **Seam file** — `.claude/tracker.md` in a deployed repo: the generated,
  backend-specific statement of how to perform the fixed tracker operations.
  The abstraction boundary between skills and backends.
- **Operation vocabulary** — the eight frozen operation names every seam file
  implements: create-issue, rewrite-issue, transition-status,
  close-with-resolution, link-parent, link-blocker, find-work, pr-linkage.
- **Universal core** — the parts of the taxonomy imposed identically on every
  repo: `type/*`, `P0`–`P3`, `status/*`, `resolution/*`, palette, invariants,
  state machines, PR conventions.
- **Adoption ADR** — the generated decision record in a deployed repo capturing
  its interview answers and deviations; the repo-local half of "drift is
  deliberate".
- **Standing rule** — an invariant expected to drift on the happy path and
  repaired after the fact: `resolution/done` backfill on auto-closed issues,
  and closing an epic when its last task closes. `project-manager` audits both.
- **Lifecycle skills** — upstream spec/ticket skills (`/to-spec`,
  `/to-tickets`) installed by the user from their own channel; consumers of the
  seam file, never part of this package.
- **Pass-through field** — a corp tracker field outside the core taxonomy
  (sprint, story points, due date) that the seam file records and skills prompt
  for exactly when the backend demands it.
- **Deliberate status** — a `status/*` value that changes only by human
  decision, versus **execution states** (in progress, in review, blocked,
  done) which the tracker maintains natively and which are never labels.
- **Graduation** — an idea becoming an epic by rewriting the same issue in
  place, so one URL carries the history from thought to shipped.
