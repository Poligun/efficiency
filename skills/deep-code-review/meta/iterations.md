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

**Copilot review on PR #1 — 4 comments, 3 valid code bugs, all fixed.**

Notable because all three were in `scope_detect.py`, the component I'd unit-checked against
two fixtures. Both fixtures happened to avoid every one of these paths, which is a lesson
about fixture coverage rather than about the script.

1. **`wire_api` ignored `build_contract_touched`** while still listing the file in `files`
   and naming it in `why`. A pure `build.rs` change reported `active: false` alongside
   "build/codegen contract touched: build.rs". Reproduced, fixed. This one mattered: a
   four-line `build.rs` edit can change every generated type in a package, and the aspect
   that should catch it was switched off.
2. **Oversized untracked files were neither scanned nor counted**, while the note claimed
   "counted, not scanned". Untracked files aren't in `--numstat`, and the read that supplies
   their line count was skipped for oversized ones. A 30,000-line new file reported
   `added: 0` and left `logic` inactive. Now line-counted without being regex-scanned, and
   the note says which happened.
3. **`compute_shape` used `or`**, so a 500-line single-file rewrite classified as
   `focused`. Copilot suggested `and`; that fixes this case and breaks the opposite one — a
   40-line change across eight files would become `standard`. Fixed by keying `focused` on
   line count alone, since the shape answers "does this fit in one context", which is about
   volume, not spread. File count still gates `deep`, where sharding needs directories.
4. **Hardcoded MCP tool name** in the PR-posting step. Partly fair — a `gh api` fallback was
   already there, so it wasn't non-actionable — but leading with an environment-specific
   tool name is brittle. Reordered to lead with `gh` and treat the dedicated tool as an
   optional upgrade.

**Lesson.** Two fixtures that both pass tell you less than they appear to. The gaps were in
untracked-file handling, oversized files, and single-file diffs — none of which either
fixture exercised. `IMPROVEMENTS.md` already carried "scope_detect.py has no tests"; this
promotes it, and the test matrix should be built from the *branches* of the code rather than
from convenient repos.

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

---

## Iteration 2 — 2026-07-31

**Goal.** Re-measure all four evals against the decontaminated skill (f586e62), replacing
iteration 1's tainted with_skill numbers. No skill changes this iteration — measurement only.

**Contamination gate.** `check_contamination.py` ran before any eval launched: CLEAN. This
is now the standing pre-run gate (TODO P0 #2): no with_skill run counts unless the checker
passed against the skill tree the run will load.

**A false start, caught by timeline forensics.** The first iteration-2 with_skill runs
(evals 2–4, executed 22:06–22:25 on 07-30) predated the decontamination commit (22:31:38).
Proof: eval-2's run-notes report as friction the absence of the exact SKILL.md paragraphs
f586e62 added ("Don't wait idly", the A3-dispatch re-keying, the Coverage skip-reason
distinction) — so the SKILL.md those runs read was pre-f586e62, i.e. still contaminated.
They are archived under `with_skill-pre-decontamination/` (their run-notes drove real
fixes and remain valuable) and excluded from the benchmark. Eval-1 with_skill had never
been run. Lesson: **a decontamination commit doesn't clean runs that already happened;
date every run against the skill tree it loaded.**

**Clean runs.** Four sequential claude-opus-5 executors (sequential to keep timing
uncontended), read-only on the fixtures, forbidden from `meta/`/`evals/`/workspace.
Baselines carried over from iteration 1 unchanged (byte-identical; they never load the
skill).

| Eval | with_skill | baseline | tokens (skill/base) |
|---|---|---|---|
| full-branch-review | **18/18** | 12/18 | 337k / 95k |
| narrowed-api-review | **8/8** | 6/8 | 259k / 65k |
| gating-dependency-bump | **5/5** | 3/5 | **34k / 47k** |
| standalone-logic-hunt | **10/11** | 5/11 | 155k / 87k |
| **total** | **41/42 (98%)** | **26/42 (62%)** | 785k / 294k |

**Headline: contamination had not inflated the totals.** The clean 41/42 equals the
contaminated 41/42 (profile shifted: eval-1 17→18, eval-4 11→10). Iteration 1's
structural conclusions stand on clean evidence now. Full analysis in
`deep-code-review-workspace/iteration-2/benchmark.md` — short version: recall parity with
baseline persists (fixture still can't discriminate must-finds), the dep-bump gap
narrowed (clean skill now flags the hand-edited lock) but TLS/MSRV still need the
`dependency` aspect, and the findings-cap ambiguity surfaced for the third time (eval-4's
one miss is a bundled roll-up table without traces; eval-1 self-counts 17 "items" where
the mechanical counter sees 14 findings).

**Environmental noise, disclosed in-run.** Eval-1 lost 8/12 verifiers to API 529s;
eval-2 hit a ~40-min harness tool outage (verification cut to 5/12, wall-clock inflated).
Both runs disclosed the degradation in Coverage and still passed everything — meaning the
assertion set tests verification's *labelling*, not its *depth*. The second fixture should
include an assertion only a verifier can settle.

**Changes for iteration 3.**
- Skill changes are unblocked now that the baseline is trusted: dependency aspect
  (TODO P1 #4), findings-cap enforcement + definition (P1 #6), scope_detect tests (P0 #3).
- Build the second fixture with subtle bugs (P1 #5) before making any recall claim.
- Keep the contamination gate mandatory before every with_skill run.
