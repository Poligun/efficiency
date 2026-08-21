# Vocabulary

Cross-skill domain vocabulary for this repo. Per-skill glossaries live in
`skills/<name>/meta/glossary.md`; a term moves here when a second skill starts
using it.

- **Seam file** — `.claude/tracker.md`: the generated, backend-specific
  statement of how to perform issue-tracker operations. Skills consume
  operations by name; backends supply implementations.
- **Standing rule** — an invariant expected to drift on the happy path and
  repaired after the fact (resolution backfill, epic close); `/project-manager`
  audits them.
- **Graduation** — an idea becoming an epic by rewriting the same issue in
  place, so one URL carries the history from thought to shipped.
