# Eval runbook

The procedure for measuring these skills. It existed only in the operator's head until
iteration 2, which cost a full set of runs (see `iteration-2/PRE-DECONTAMINATION-NOTE.md`).
Follow it in order; the steps that exist because something went wrong say so.

## 0. Contamination gate — before anything else

```bash
python3 ../check_contamination.py   # from this directory; must print CLEAN, exit 0
```

Run this against the exact skill tree the executors will load, immediately before
launching runs — not after, and not from memory of having run it once. A decontamination
commit does not clean runs that already happened: iteration 2's first with_skill batch was
executed 6–25 minutes before the decontamination commit landed and had to be discarded.
`build_benchmark.py` re-runs this gate at assembly time and refuses to build if it fails,
but assembly-time is the backstop, not the gate.

Record which commit of the skill tree the runs load (`git rev-parse HEAD` plus
`git status --porcelain` on the skills repo — a dirty tree means the runs load something
no commit identifies).

## 1. Fixture state

- `ninniku` (evals 1, 2, 4): branch `cel-alert`, working tree dirty in exactly the way
  `iteration-N/ninniku-baseline-gitstatus.txt` records — the uncommitted changes are part
  of the branch under review. Verify before and after every run; byte-identical or the
  run is invalid.
- `fixtures/dep-bump-repo` (eval 3): branch `chore/bump-deps`, clean tree.

## 2. Executor runs

One fresh agent per run (`claude-opus-5` to match prior iterations — record any change of
model in the benchmark caveat), **sequentially**, so wall-clock and token measurements
never contend with a sibling run. Each executor gets:

- the eval's user prompt **verbatim** from `<skill>/evals/evals.json` / the iteration's
  `eval_metadata.json`;
- the skill's SKILL.md path (with_skill) or no skill mention at all (without_skill);
- hard constraints: read-only on the fixture; no reads under `skills/*/meta/`,
  `skills/*/evals/`, or this workspace (assertion leakage invalidates the run); outputs
  written only to `iteration-N/eval-*/<config>/outputs/{report.md,run-notes.md}` (the
  Write tool may refuse workspace paths for subagents — a Bash heredoc is the accepted
  fallback);
- the run-notes request: aspects/angles run vs skipped, subagent counts and models,
  finding-pipeline counts, friction ordered by time cost, compliance section, `## Stats`.
  Run-notes have historically been worth more than the reports — never skip them.

The executor must never see assertions, ground truth, or another run's output.

After each run write `timing.json` next to `outputs/`: `total_tokens`, `duration_ms`,
`total_duration_seconds`, `tool_uses`, subagent count, `findings_reported`, and a `note`
naming the executor model and any environmental degradation (API errors, harness outages)
— degradations must also appear in the report's own Coverage line, but the reader of
benchmark numbers looks here first.

## 3. Grading

1. Mechanical first: `python3 check_report.py <report> --repo <fixture>
   [--baseline-status iteration-N/ninniku-baseline-gitstatus.txt]` →
   `grading_mechanical.json`. It is authoritative for anchor existence, finding count,
   label presence, and worktree cleanliness — subject to its known artifacts (abbreviated
   prose paths, external-repo references, the zero-findings short report shape).
2. Model grading: one fresh grader agent per run (`claude-opus-5`), given the assertion
   list, the report (only — not the run-notes), the ground-truth file
   (`<skill>/meta/ground-truth/…`, whose Corrections section supersedes the rest), and
   the mechanical results. Output `grading.json` in the exact
   `{eval_id, configuration, pass_rate, passed, failed, total, expectations:[{text,
   passed, evidence}]}` shape — `build_benchmark.py` reads it literally.
   Graders may spot-verify against the fixture, read-only.

## 4. Assembly

```bash
python3 build_benchmark.py iteration-N
```

Writes `benchmark.json` + `benchmark.md` (runs the contamination gate first; records the
result in metadata). Set the iteration's history honestly in `iteration-N/caveat.txt` —
carried-over baselines, archived runs, environmental noise. Then append the analyst pass
to `benchmark.md`: which assertions discriminate, where the skill did worse, what the
numbers do NOT show. The analyst pass is the part people re-read; the totals are not.

## 5. Record

Append the iteration entry to `<skill>/meta/iterations.md` (what changed, the table, the
lessons, changes for next iteration) and update `skills/TODO.md`. Commit runs + grading +
benchmark + docs together, so a checkout at any commit shows numbers consistent with the
skill tree beside them.
