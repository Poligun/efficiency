# Cross-skill TODO — ranked by expected impact

A holistic pass over `deep-code-review`, `business-logic-review`, and `repo-index`
(2026-07-30), merging the per-skill `meta/IMPROVEMENTS.md` backlogs with new findings and
ordering them by how much addressing each first would improve the skills. Per-skill files
keep the detail; this file owns the ranking.

The ranking follows from three facts the iteration-1 benchmark itself established:

1. **Recall is not where the skills win** — a capable baseline found the same bugs. The
   wins are structure, precision, and disclosure, bought at ~2× tokens and ~3× wall-clock.
2. **Every headline number is from contaminated runs.** Iteration 2 (clean re-measure) was
   started but never finished — the workspace has empty `with_skill/outputs/` dirs.
3. **The one measured regression vs. baseline** is the dependency-bump gate: 1.6× cheaper,
   6× faster, and it missed a TLS-backend swap, an MSRV jump, and a broken lockfile.

So: first make the measurements trustworthy, then close the known quality gap, then attack
cost (the adoption blocker), then hygiene.

---

## P0 — Restore trust in the data (everything else is prioritized on it)

- [ ] **1. Finish the iteration-2 clean re-run.** All benchmark numbers cited anywhere
      (98% vs 62%, per-eval tables) come from the contaminated skill; iteration 2 is
      half-executed in `deep-code-review-workspace/iteration-2/` (baselines done, most
      `with_skill` runs missing). Until this lands, treat iteration-1 with_skill figures
      as an upper bound and don't use them to justify design choices.
- [ ] **2. Wire `check_contamination.py` into the eval flow as a mandatory pre-run gate.**
      The script exists precisely because a hand-run grep wasn't enough, yet nothing runs
      it automatically. One line in the eval procedure ("run it; abort on exit 1") converts
      a lesson into a mechanism.
- [ ] **3. Test suite for `scope_detect.py`.** Already promoted to top of
      `deep-code-review/meta/IMPROVEMENTS.md` and still unstarted. It is the deterministic
      backbone every review gates on, and it has already shipped three silent bugs that two
      fixtures missed. Table-driven, one synthetic git repo per case, matrix built from the
      code's branches: every role, every signal, every aspect predicate, both shape
      boundaries, untracked/oversized/binary/renamed files, detached HEAD, no-trunk.

## P1 — Close the known quality gaps

- [ ] **4. Add the `dependency` aspect to deep-code-review.** The only measured case where
      the skill did *worse* than baseline. Activate on `dep_major_bump` or a lockfile-only
      change; one cheap agent asks: what changed in the bumped packages' default features,
      does the MSRV/toolchain move, does the lock actually resolve (`cargo check --locked`
      or ecosystem equivalent). Keeps the early-stop cost win while closing the
      supply-chain hole. Sketch already in `deep-code-review/meta/IMPROVEMENTS.md`.
- [ ] **5. Build a second eval fixture with subtle bugs.** 26 of 42 assertions —
      including nearly all must-find ones — don't discriminate skill from baseline, so
      recall changes are currently unmeasurable. Blocks any evidence-based decision on
      angles, language-specific passes, or merging A1/A2. (Also: `repo-index` has **no
      evals at all**, yet it owns the knowledge-base contract both review skills read —
      at minimum a smoke eval that indexes a small fixture and checks INDEX.md validity.)
- [ ] **6. Make the findings cap real, and reconcile it.** The ~15 cap failed in *both*
      configurations (17 and 27) — a stated-then-ignored cap teaches the model every other
      cap is soft. Either enforce it as an explicit truncation step in Step 7 (count,
      cut, disclose in Coverage) or delete it. While there: `severity-rubric.md` says ~15,
      `business-logic-review/references/output-contract.md` says ~12 — if the BLR cap is
      deliberately tighter because its findings merge into the ~15, say so in one sentence;
      right now it reads as drift.

## P2 — Cost and latency (the adoption blocker: ~2× tokens, ~3× wall-clock)

- [ ] **7. Reuse a fresh `conventions.md` to skip deep-code-review Step 3.** The first
      real repo-index integration payoff — converts a per-review grep pass into a per-repo
      one. Needs a freshness rule that's actually trustworthy; the minimal version is
      cheaper than full incremental re-index: `git log <last-verified-sha>..HEAD -- <probed
      paths>` empty → fresh, else re-probe only the touched rules.
- [ ] **8. Track finding provenance (angle + agent) through to the report.** Cheap to add
      (both output schemas already carry `angle`), and it is the prerequisite for every
      evidence-based cut: whether A1/A2 merge into one Opus call, whether A10 earns its
      false-positive rate, which angles never fire. Add a per-run tally to the eval
      run-notes so yield accumulates across iterations.
- [ ] **9. Decide the A1/A2 merge with data from #8.** Two Opus calls that corroborate
      often; if merged findings match separate-run quality on the new fixture, that's the
      single largest token cut available in round 1.

## P3 — Correctness and robustness details

- [ ] **10. Single source of truth for the establishment test.** It's spelled out in four
      places (`deep-code-review/SKILL.md`, its README, `convention-probes.md`,
      `repo-index/SKILL.md`). The next tweak to the ratio rule will miss one of them.
      Keep the normative statement in one reference file; everywhere else links or quotes
      with a pointer.
- [ ] **11. Small `scope_detect.py` fixes** (roll into #3's test matrix):
      - `OPENAPI_REQUIRED_RE` is defined and never used — dead code or a missing feature;
        decide which.
      - `dep_major_bump` notes don't name their source manifest (painful on multi-manifest
        waves) — prefix with the path. *(already in IMPROVEMENTS)*
      - `TEST_NAME_RE` classifies helpers like `test_utils.py` as tests, exempting them
        from convention/API review.
      - `logic` activates only at ≥25 changed code lines: a 10-line bugfix branch gets no
        logic review from this skill. Fine if intentional (built-in `/code-review` covers
        it) — but state that in SKILL.md Step 1 so the gap is a documented handoff, not an
        accident.
- [ ] **12. Exercise business-logic-review's standalone (human) mode.** Everything so far
      was measured through subagent dispatch; the human-mode path (memory approval flow,
      questions section, proposed-diff UX) has never been run against a real user.
      *(already in IMPROVEMENTS — promoted here because standalone use is the skill's own
      trigger description)*
- [ ] **13. Position explicitly against the built-in `/code-review`.** The SKILL.md's
      premise ("built-in hunts line-level bugs well; this judges design") matches what the
      benchmark showed — baseline recall was fine. Add a short "when to use which" note to
      the READMEs: built-in for quick bug hunts on small diffs (also the ≤25-line gap in
      #11), these skills for design/convention/memory-accumulating review. Consider whether
      A3's six core angles should eventually delegate the pure line-level portion rather
      than duplicate it.

## P4 — Larger directions (unchanged from per-skill backlogs, still worth keeping)

- Post-merge outcome tracking (which findings did authors act on) — the only true measure.
- "Review the review" completeness-critic pass.
- Language-specific angle layers that compose with the agnostic core.
- repo-index incremental re-index, L3 per-file memos, lessons.md harvesting.
- Feed verifier REFUTED verdicts back into `false-positives.md` automatically.
- Removed-behavior angle as a first-class citizen (refactor branches).
