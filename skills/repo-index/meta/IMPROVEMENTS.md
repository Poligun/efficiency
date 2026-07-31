# repo-index — improvement checklist

Iteration 1 is deliberately a stub. What matters is that the *contract* is right — the
entry schema, `INDEX.md` as the sole routing entry point, and the layer numbering — because
those are what `business-logic-review` and `deep-code-review` already read, and changing
them later means migrating live knowledge bases.

## Next up

- [ ] **Incremental re-index.** Store `last_indexed_sha` in `INDEX.md`; on re-run, drive
      updates from `git log <sha>..HEAD --name-only` rather than re-walking everything.
      This is the single change that makes the skill usable on a repo that's actively
      changing, and everything else below assumes it.
- [ ] **Per-file memos (layer L3).** What each significant file is for, its gotchas, its
      non-obvious invariants. Needs a staleness budget — memos rot faster than anything
      else here, so they need a churn threshold below which a file doesn't get one.
- [ ] **Selective depth on recall.** Let a consuming agent request "L0 only" vs "L0+L2"
      explicitly rather than inferring it. Would make the layering pay off for cheap agents.
- [ ] **`lessons.md` harvested from review findings.** After N reviews, patterns emerge —
      "this codebase's error handling swallows failures in three places". Promote recurring
      finding classes into a lesson so future reviews start from it.

## Bigger, later

- [ ] **Background full walk** via `/loop`, chunked so it never blocks an interactive
      session. The obvious design is a work queue in `INDEX.md` with a resumable cursor.
- [ ] **Confidence decay.** A claim nothing has re-verified across N reviews gets demoted,
      not deleted. Complements the change-triggered staleness check, which only catches
      claims whose anchor file was touched.
- [ ] **Let `deep-code-review` skip its convention grep pass** when `conventions.md` is
      fresh. The first real integration payoff — it turns a per-review cost into a
      per-repo one. Blocked on incremental re-index being trustworthy enough that "fresh"
      means something.
- [ ] **Call-graph / dependency edges between domains.** Would let a reviewer see blast
      radius without tracing it by hand every time.
- [ ] **Detect and record what CI already enforces** (lint configs, type checkers, test
      gates) so review skills can automatically exclude those findings instead of carrying
      a hand-written exclusion list.

## Open questions

- Should `architecture.md` be generated fresh each time or edited incrementally? Fresh is
  simpler and avoids drift; incremental preserves human edits. Leaning fresh with a
  clearly-marked "human notes" section that's never overwritten.
- Where's the line between this and a repo's real `docs/`? Current answer: this is for
  agents and may carry unconfirmed material, `docs/` is for humans and may not. That holds
  for now but will get tested once `architecture.md` is good enough that a human wants to
  read it.
- Monorepos with genuinely independent packages might want per-package knowledge bases
  after all. Deferred until someone hits it.
