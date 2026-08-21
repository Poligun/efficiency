# Open questions

Deferred, not forgotten. Round numbers follow the design's rollout state.

## Round 2 — the corp backends

- **Jira seam implementation.** The design handles per-project variability
  structurally (discovery-generated seam file, per-transition constraints,
  pass-through fields), but no adapter exists. Needs a live Jira instance with
  MCP or CLI access to build and test against. Open sub-questions: how much of
  the vocabulary maps to native fields per instance (issue types, priorities,
  workflows, resolutions are all admin-configurable); whether `rewrite-issue`
  graduation survives Jira's issue-type-change restrictions; where the
  vocabulary doc lives when docs are in Confluence rather than the repo.
- **Confluence as the doc layout.** The doc-layout interview question currently
  assumes repo paths. A corp answer may be Confluence spaces; the vocabulary
  doc's pointer sections would need URL targets and the "issues are thin
  pointers" tenet re-examined against Confluence's own draft/review lifecycle.
- **Slack's role.** Probably a notification/reporting surface for
  `project-manager` output rather than a tracker backend. Unexplored.
- **Plugin packaging.** The corp distribution vehicle (marketplace-installable)
  once a second backend exists to justify it.

## Evals

- **pm-setup eval.** Needs fixture repos: fresh (no labels/issues), stock
  -labeled with open issues (migration path), already-bootstrapped (refresh
  path), and one with a pre-existing PR template and CLAUDE.md (merge path).
  Score: labels created/deleted correctly, no `{{` markers survive, AGENTS.md
  pointer present, migration proposals sane.
- **project-manager eval.** Needs a tracker seeded with known violations
  (missing resolutions, all-tasks-closed epics, double labels, prefix
  mismatches) and a known frontier; score recall on violations and the
  fix-batch's correctness. Blocked on deciding whether seeded fixtures live as
  a scratch GitHub repo or as recorded `gh` output.

## Smaller

- **Label-sync target.** Scarlet's ADR deferred a declarative label-sync until
  the set churns. If the palette or families ever change, re-running pm-setup's
  refresh path covers it; revisit only if that proves clumsy.
- **`/grill-with-docs` dangling reference** (adjacent, not this skill): it
  points at a `domain-modeling` skill that doesn't exist and its own skill dir
  is empty. Fix or delete separately.
