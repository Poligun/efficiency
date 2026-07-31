# Iteration log

One entry per iteration: what changed, what the numbers said, what the user said, and the
lesson. Keep the lessons — they're what makes iteration N+1 better than a rewrite.

---

## Iteration 1 — 2026-07-29

**Built.** Initial version of all three skills. `deep-code-review` orchestrator (8 steps,
4 agent role files, 3 references, `scope_detect.py`), `business-logic-review` (10 named
angles, memory protocol, dual output contract), `repo-index` stub.

**Design source.** `decisions.md` for the reasoning, `ground-truth/ninniku-cel-alert.md`
for the eval target.

**Verified before evals.**
- `scope_detect.py` against `ninniku@cel-alert`: `shape: standard`, all four aspects
  active+strong, `code_lines` 1215 (correctly excluding 1112 lines of lockfile churn),
  `wire_breaking` on `account_info.proto`, `dep_major_bump` × 3.
- Gating against a synthetic dependency-bump branch: all four aspects inactive,
  `code_lines: 0`, major bump still surfaced as a note. This is the behavior that keeps
  the skill cheap on the branches where it has nothing to say.
- Exit codes: 2 (not a repo), 4 (empty range).

**Bugs found and fixed during the unit check** — all three would have degraded the review
silently rather than failing loudly, which is the worst kind:

1. **`@{upstream}` as the preferred base.** On a pushed feature branch it resolves to the
   branch's own remote ref, so the diff collapsed to only uncommitted work — a review that
   would have looked like it ran fine while seeing almost nothing. Fixed by preferring
   trunk refs and skipping any candidate that's an ancestor-equal of HEAD.
2. **`committed` and `worktree` were mutually exclusive.** A file added in a commit *and*
   further edited in the working tree is both. This matters because it routes PR comments.
3. **`wire_breaking` false-positived on re-indentation.** A proto field moved into a
   `oneof` shows up as removed+added; flagging it would have trained the reader to ignore
   the signal. Fixed by checking whether the field name survives elsewhere in the hunk.

**Correction to planning-stage ground truth.** An exploration agent reported "private
`mod x;` + `pub use x::Type;` is established 12:2." First-hand counting gives 12 `pub use`
against 10 `pub mod` — under 3:1, so `mixed`, not `established`. The finding it would have
justified isn't clean. Recorded in `ground-truth/#corrections`.

**Lesson.** Verify subagent counts before building assertions on them. The establishment
test caught this exact class of error, which is mild evidence the mechanism is doing its
job — but it only worked because someone counted. A skill that trusted the reported ratio
would have filed a finding the codebase contradicts.

**Evals.** 4 evals × 2 configurations, 8 runs, 42 paired assertions.

| Eval | with_skill | baseline | tokens (skill/base) |
|---|---|---|---|
| full-branch-review | 17/18 | 12/18 | 207k / 95k |
| narrowed-api-review | 8/8 | 6/8 | 128k / 65k |
| gating-dependency-bump | 5/5 | 3/5 | **30k / 47k** |
| standalone-logic-hunt | 11/11 | 5/11 | 248k / 87k |
| **total** | **41/42 (98%)** | **26/42 (62%)** | 613k / 294k |

**The result that matters isn't the totals.** 15 assertions discriminate, 26 don't, 0
favour the baseline — and the 26 non-discriminating ones are mostly the *must-find*
assertions. Both configurations locate the injection, the lifecycle gap, the missing dedup,
the silent fallbacks, the unwired surface.

So **recall is not where this skill earns its cost.** All 15 discriminating assertions are
about structure, precision, and disclosure: labelled and anchored findings, a Coverage
statement admitting what didn't run, execution traces, not falling for the missing-tests
trap, not inventing findings about untouched code, and declaring a branch un-reviewable
rather than manufacturing content. That costs ~2× tokens and ~3× wall-clock.

**Caveat on the numbers.** The with_skill runs used the contaminated skill (see below).
Findings matching the leaked examples are not independent evidence. Iteration 2 re-measures
against the clean version and the with_skill figures may move down.

**Six defects the eval run-notes found in the skill, all fixed:**

1. **Contamination** — skill files carried examples lifted from the eval target, including
   one keyed to an *uncommitted* change and a **fabricated** `user-quote` in the memory
   template. An agent could emit several must-find assertions without reading code. An eval
   agent caught it and correctly discounted its own findings. All examples are now
   synthetic. See `decisions.md` for why rejecting a worked-example *file* didn't prevent
   this.
2. **Broken base-detection snippet** — `A && echo X || B && echo Y` prints both, giving a
   two-line `BASE` and a failing `merge-base`. Reproduced, replaced with a loop.
3. **Verify-before-dedup** — the 12-verifier budget was spent on duplicates (one run
   deduped 42 raw findings to 22 *after* verifying). Dedup now precedes verification.
4. **Establishment-test gap** — support ≥3 with >1 counterexample at ratio ≥3:1 matched no
   rule. Real data hit it: a 34-vs-4 error-type pattern fell through and got defensively
   demoted to `mixed`. Rules are now ordered and total, with a ratio band.
5. **No verifier model tiers** were specified; a run picked sonnet for all 12 by default.
6. **Unbounded subagent concurrency assumed** — the 20-agent cap was hit in two runs, and a
   silently dropped verifier means a finding ships stamped verified. Now batched.

**Ground-truth correction.** I recorded the CEL injection as CRITICAL. A with_skill run
argued it to MEDIUM by establishing that `NativeTrigger.expression` already accepts
arbitrary CEL from the same caller, so no privilege boundary is crossed. That reasoning is
better than mine; the baselines mostly made the unexamined-CRITICAL call. The assertion now
tests the defect, not the severity.

**User feedback.** Reviewed all 8 runs, no comments, LGTM.

**Lessons.**

- **Audit for eval-target contamination *before* running evals, not after.** `grep` the
  skill tree for identifiers from the fixture repo. Examples get written while the author's
  head is full of the case they just debugged, and that case is the eval target.
- **Run-notes from eval agents are worth more than the reports.** Every one of the six
  defects came from asking agents to report friction, not from reading their output. Keep
  requesting them.
- **A capable baseline is the point.** These baselines found the bugs; had they been weak,
  the 98%-vs-62% headline would have looked like a win it isn't.

**Changes for iteration 2.**

- Re-run all 4 evals against the de-contaminated skill; treat iteration 1's with_skill
  numbers as an upper bound.
- Add a second fixture with subtler bugs — the must-find assertions have no discriminating
  power on this one.
- Decide the `≤15 findings` cap: enforce it as a truncation step or drop it. It failed in
  **both** configurations (17 and 27), and a stated-then-ignored cap teaches the model that
  the other caps are soft.
- Consider the `dependency` aspect (see `IMPROVEMENTS.md`) — gating was cheaper on the
  dep-bump branch and missed real supply-chain risk.
