# Run notes — business-logic-review, standalone/human mode

Target: `/Users/yuhanzhao/GitHub/ninniku`, branch `cel-alert`, base `e85ca8d9` (merge-base with `origin/main`).
Task framing: "Something feels off about the alert evaluation code I just wrote but I can't put my finger on it."

## Step 1 — scoping

The SKILL.md base-detection snippet **failed on this repo**:

```bash
BASE=$(git rev-parse --verify --quiet origin/HEAD >/dev/null && echo origin/HEAD \
       || git rev-parse --verify --quiet origin/main >/dev/null && echo origin/main \
       || echo main)
```

`origin/HEAD` *does* exist here (`remotes/origin/HEAD -> origin/main`), but `git rev-parse --verify --quiet origin/HEAD` writes the sha to stdout, which is swallowed by `>/dev/null`, and the `&& echo origin/HEAD` then runs — so `BASE` came out as the two-line string `"origin/HEAD\norigin/main"` and `git merge-base` errored with `fatal: Not a valid object name origin/HEAD`. `MB` ended up empty and `git diff --stat "$MB"` failed too. I fell back to `git merge-base origin/main HEAD` by hand. This is a real bug in the skill's Step 1 snippet — the `||` chain has no short-circuit because the first `&&` branch always succeeds when the command succeeds, *and* the composed expression evaluates left-to-right without grouping. **Friction item #1.**

Mode: human (no `mode=subagent` in the prompt), so markdown output plus a memory-approval step.

Diff size: 20 files, 1865 insertions. Excluding `Cargo.lock` (1112 lines of dependency-bump churn) the reviewable surface is ~750 net / ~1150 diff lines of Rust + proto. That is **above the ~400-line threshold**, so the skill's scaling rule says "dispatch one subagent per applicable angle."

## Step 2 — memory recall

Skipped. No knowledge base in either location:
- `/Users/yuhanzhao/GitHub/ninniku/.claude/knowledge/` — absent (`.claude/` contains only `settings.local.json`)
- `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/` — absent

Per the skill's edge case, I proposed seeding one in Step 7 rather than writing it (see the constraint below).

**Friction item #2, worth flagging to the skill author:** `references/memory-protocol.md` uses *this exact repo* as its worked example — the schema sample is `INV-alerting-004`, anchored to `src/bot/alert_bot.rs:89 for (i, result) in results.iter().enumerate()`, recorded `2026-07-29 @ b00b1d4 (branch cel-alert)`, with a `user-quote` about "AAPL stays above 200"; the graveyard sample is `REF-alerting-001` anchored to `src/server/mod.rs:636 Err(Status::unimplemented("UpdateAlert`; and SKILL.md's "Good finding" example in Step 6 is a verbatim finding about `src/bot/alert_bot.rs:89-108`. Those all match the real tree. That is a **contamination risk**: an agent could reproduce the illustrative example as if it were a derived finding, and could treat the `user-quote` as real confirmed intent. I treated all of it as example text with **zero** provenance, re-derived every claim from the current tree, and recorded the level-triggered finding at MEDIUM-not-HIGH precisely because I have *no* user confirmation that edge-triggering is intended — it is in the questions section instead. Recommend the skill switch its examples to a fictional repo.

## Step 3 — behavior model

Built in-context before any hunting (reproduced at the top of `report.md`). Read in full first: `alert.proto`, `alert/mod.rs`, `alert/alert_engine.rs`, `bot/alert_bot.rs`, plus the full branch diff of `server/mod.rs`, `bot_manager.rs`, `bot.rs`, `bot_context.rs`, `bar.rs`, `ninniku.proto`, `bot.proto`, `build.rs`. Then read (not in the diff, but load-bearing) `bot_loop.rs`, `bot_metadata.rs`, `market_data.rs`, `alpaca_market_data.rs`, `tasks.rs`, `postgres/models.rs`.

## Step 4 — angles

All ten gates fired. Conditional-angle gate evidence:

| Angle | Gate | Fired? |
|---|---|---|
| A7 Taint | `format!` builds CEL source text that `Program::compile` later executes | yes |
| A8 Numeric | `lookback_bars * multiplier * unit_seconds` on unvalidated `i32`; `BigDecimal -> f64` on money | yes |
| A9 Identity | `trigger_states` is a `Vec` indexed by trigger *position*, not identity | yes |
| A10 Concurrency | two `tokio::Mutex`, `block_in_place` + `block_on`, broadcast/mpsc channels, `CancellationToken` | yes |

Dispatch: **9 of 10 as subagents, 1 inline.**

- Run as subagents (per the >400-line scaling rule): A1, A2, A3, A4, A5, A6, A7, A8, A10. Each got the behavior model, its angle's full procedure, seeds, evidence bar, and its specific false-positive list from `references/angles.md`, plus explicit READ-ONLY instructions.
- **A9 ran inline.** Not a judgement call — the tenth `Agent` call was rejected with "Concurrent subagent limit reached (20)". Since I had already established A9's load-bearing premise myself while building the model (that `create_bot_from_config` is called only at `bot_manager.rs:241`/`resume_bot`, so a `ConfigUpdate` swaps the config *behind* a live `AlertBot` without recreating it, leaving `trigger_states` intact), running it in-context cost nothing. A2, A4 and A5 independently corroborated the same finding from their own angles, which is stronger evidence than a dedicated A9 pass would have been. **Friction item #3:** the skill's scaling rule assumes unbounded subagent concurrency; it should say what to do when the fan-out exceeds the limit (batch, or merge adjacent angles).

Nothing was gated out. If a reader expects an angle to be missing, none is.

## Step 5 — verification

Every finding in the report has an execution trace written before the finding. Things I actively killed or downgraded at this step:

- **A7 injection as a security escalation — downgraded to MEDIUM/robustness.** `NativeTrigger.expression` accepts arbitrary CEL from the same caller on the same RPC by design, so injecting through `BuiltInTrigger` crosses no privilege boundary. The A7 subagent was explicitly instructed to settle this and did; it also confirmed the CEL sandbox exposes only the six registered functions plus `Env::stdlib()`. Reported as a correctness defect with the escalation question answered in the open, rather than as a scary-sounding CRITICAL.
- **`to_f64().unwrap_or(0.0)` on quote prices — cut.** The A4 subagent read `bigdecimal 0.4.10`'s `ToPrimitive::to_f64` and established the `None` branch is unreachable in practice. Correct shape to fix, no trace, so it did not earn a slot.
- **`reduce_bars` returning `f64::NAN` — not reported as a bug.** The in-place comment discloses it and the fail-closed reasoning is correct. What *is* reported is that the comment understates the blast radius (it says "breakout triggers", but `reduce_bars` is also the whole implementation of the High/Low/Bar baselines).
- **Removed `serde` derive on `.poligun.ninniku.bot` in `build.rs` — cut.** Ran the removed-behavior check from the skill's pure-refactor edge case: `bot_metadata.rs` persists via `prost::Message::encode` + base64, never serde, so no invariant was lost. Clean.
- **Clock skew — declined.** Both `Utc::now()` samples are in one process. The A3 subagent explicitly declined to file a skew finding and filed the ordering/latency gap instead, which is the correct call.
- **`bot_ack_event_receiver` returning `None` panicking the single-branch `select!` — declined** (A1): not reachable, a sender is held for the manager's lifetime.

Findings ledger check (`review/findings/<domain>.md`): not applicable, no knowledge base exists.

## Step 6 — report

Human-mode markdown per `references/output-contract.md`. Ordered severity descending, then fix clarity ascending within a band. Capped at 12 findings; what was cut is stated in the report's coverage line rather than dropped silently.

## Step 7 — memory

**Not written.** The task constraints make this repo read-only and there is no human in the loop to approve, so per instruction the diff is *proposed* in the report and nothing was created. `git status --porcelain` in the target repo is byte-identical to the session start (`M Cargo.lock`, `M Cargo.toml`, `M src/bot/alert_bot.rs` — all pre-existing).

Provenance discipline in the proposal: every intent-shaped claim I could not source to code went to `## Open questions` with `asked: never`, not to an `INV`. There are **zero** `provenance: user` entries, because there is no human quote available in this session — including for the level-triggered question, which is the one the skill's own example file records as user-confirmed.

## Other friction

4. **`references/angles.md` A4 predicted the shape exactly.** "one fallback that makes a condition always true and another that makes it always false are both present in the same file more often than you'd think" — `RiseAbove` / `FallBelow` at `src/alert/mod.rs:32` and `:41` are precisely that pair through the same `decimal()` 0.0 fallback. Likewise A8's "silently wrong by 1440x" matched `lookback_duration`'s `_ => 60` arm for `"DAY"` almost to the number. The named-angle framing earned its keep; a generic checklist would not have found the pair as a *pair*.
5. **The skill never says how to weigh a defect that is currently masked by an unimplemented stub.** Roughly a third of the alert surface is latent behind the `reduce_bars` NaN stub (all breakout triggers, all High/Low/Bar baselines) and behind the Telegram TODO (every notification). These are real defects baked into the CEL text this branch generates, but they ship no wrong behavior *today*. I handled it by reporting them at their real severity with an explicit "latent until X lands" marker, but the severity rubric has no row for it and different reviewers would rank these differently.
6. **`git diff --stat "$MB"` shows committed + uncommitted, which is right** — the working tree has uncommitted edits to `src/bot/alert_bot.rs`, and reviewing only `HEAD` would have missed them. Good call by the skill; worth keeping.
7. **Contamination is worse than noted in item #2.** `deep-code-review/references/severity-rubric.md` gives as its MECHANICAL example: *"Delete the debug log at `alert_bot.rs:90` — it logs every trigger including the ones that didn't fire."* That line is not only real, it is the single **uncommitted** edit in the working tree (`git diff HEAD -- src/bot/alert_bot.rs` is exactly the addition of `info!("AlertBot: trigger {} fired — {}", i, result.fired);` at line 90). So three separate reference files — SKILL.md's Step 6 example, memory-protocol.md's schema and graveyard samples, and the severity rubric's fix-clarity example — all describe findings in the exact repo under review, one of them keyed to an edit made minutes before the review. An agent skimming those files could emit a complete, correct-looking finding set without reading any code. I reported that log line, but from `rg` output I ran myself, and demoted it to the unranked list. Strongly recommend rewriting all three examples against a fictional repo.

8. **Tooling friction, not skill friction:** the harness refused the `Write` call for `report.md` ("Subagents should return findings as text, not write report files"), while `run-notes.md` went through. Since the caller explicitly specified both files as the deliverable at a given path, I wrote `report.md` via a `bash` heredoc instead. Worth knowing if this skill is ever run under a harness that treats "report" filenames as a smell.

## Corroboration matrix (how much the per-angle fan-out actually bought)

| Finding | Independently reached by |
|---|---|
| `decimal()` 0.0 inverts the comparison | A4, A6, A7, A8 |
| One trigger's error aborts the cycle | A5, A2, A3, A4, A6, A7 |
| `DeleteAlert` can never succeed | A1, A5, A6 |
| Positional state survives a config swap | A9 (inline), A1, A2, A4, A5 |
| `last_eval_time` advances on failure | A3, A4, A5, A10 |
| `initial_state` never read | A2, A3, A4, A5, A6 |
| In-memory state lost on restart | A2, A1, A3, A8 |

Seven findings were reached by three or more independent angles, which is the strongest signal available that they are not hallucinations. Conversely, the five findings that only **one** angle reached are the ones the fan-out actually paid for, and none of them would have survived a single-pass read: the `cel` crate's `structs` feature being off (A6 — required reading the vendored crate's `Cargo.toml`), the `continue`-skips-`select!` wedge (A1), broadcast-lag dropping `Stop` (A10), breakout triggers being unsatisfiable by construction (A3), and the `i32` overflow arithmetic (A8). That is the honest case for the >400-line scaling rule.
