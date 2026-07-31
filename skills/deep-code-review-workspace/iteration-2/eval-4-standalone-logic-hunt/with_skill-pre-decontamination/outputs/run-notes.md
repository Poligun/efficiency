# Run notes — business-logic-review, standalone (human) mode

Target: `/Users/yuhanzhao/GitHub/ninniku`, branch `cel-alert`.
Base resolved by the skill's Step 1 loop: `origin/HEAD`, merge-base `e85ca8d9bfbfcb5571e185f6b7a4587cb923360c`.
Diff: 20 files, 1865 insertions — but 1112 of those are `Cargo.lock`. Reviewable surface is
~700 lines of Rust + ~300 lines of proto.

## Mode detection

Prompt did not say `mode=subagent`, so human mode: markdown report, questions section,
and a *proposed* memory diff that I do not write. (The launching prompt also explicitly
forbade writing, which agrees with the skill's "wait for approval" instruction — so no
conflict arose.)

## Step 2 — memory recall

No knowledge base at either location:
- `/Users/yuhanzhao/GitHub/ninniku/.claude/knowledge/` — absent (`.claude/` contains only `settings.local.json`)
- `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/` — absent

There *is* a `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/memory/` directory, but that
belongs to the harness's own memory tool, not to this skill's `knowledge/` schema. I did not
read it: it is not the artifact Step 2 describes, and one of its filenames suggested it might
contain eval-harness bookkeeping that would contaminate the run.

Consequence: the whole review ran with zero priors. Every intent question below is genuinely
open, and Step 7's output is a seed proposal rather than an update.

## Angles: what ran, how, and why

Skill scaling rule: "Under ~400 changed lines, run the angles as an in-context checklist…
Above that, dispatch subagents." Non-lockfile diff is ~1000 lines, so above the line. But the
*coherent* part — the alert engine + translator + bot — is ~670 lines and the whole review
turns on holding one behavior model across all three files. So I split it: core angles inline,
two verification-heavy angles delegated.

| Angle | Where it ran | Why |
|---|---|---|
| A1 Lifecycle | inline | needs the create→start→delete call sequence across 4 files; a subagent would have had to rebuild the same model |
| A2 Repeat-fire | inline | same; the negative grep is one command |
| A3 Boundary/window | inline | small surface (`last_eval_time`, `now`, `interval`) |
| A4 Fallback/sentinel | inline | highest-yield angle, and it needed the behavior model to trace sentinels into decisions |
| A5 Partial failure | inline | one loop, one `?` |
| A6 Declared surface | **subagent** (Explore) | ~12 declared names × repo-wide greps, plus `target/` generated-code disambiguation. Pure fan-out, exactly what the skill says to delegate. Returned a clean table; every claim I use from it I re-anchored against code I had already read. |
| A7 Taint | **subagent** (Explore) | gate fired (`format!` building CEL). Needed a dependency-source dig into the vendored `cel` crate that I did not want in my context. |
| A8 Numeric domain | inline | gate fired (`lookback_bars * multiplier * unit_seconds`, `Duration::seconds`, float money) |
| A9 Identity/correlation | inline | gate fired (`states[i]` positional); needed the config-update path model |
| A10 Concurrency | inline, **mostly gated down** | gate fired (`block_in_place`, `Mutex`, broadcast channel) but the angle's own rule — "if you can't name the other task, don't report it" — killed most candidates. Only the create_bot read-then-write TOCTOU had a nameable second actor, and I cut it as pre-existing. |

Both subagents ran concurrently, neither was refused, no concurrency cap was hit.

## Independent verification I ran myself

Even where a subagent reported a negative, I re-ran the load-bearing greps inline
(`cooldown|dedup|…`, `trigger_states|next_state`, `get_highest_high`) — the skill's
"memory primes your questions, it doesn't answer them" applies equally to subagent output.
Two extras neither agent covered:
- `~/.cargo/registry/.../chrono-0.4.4*/src/time_delta.rs:208-215` — confirmed `Duration::seconds` panics.
- `src/tasks.rs:36,49` — confirmed a panicking background task is only logged at shutdown, never restarted.

## Findings cut to stay near the 12-finding cap

Stated in the report's coverage line too. Cut: `EvalSchedule.interval` non-positive → 5s
error-loop forever (folded into the interval finding); `Alert` proto message declared and
never used plus its incorrect doc comment; the `info!("trigger {} fired — {}")` line that
logs non-fired triggers (the one uncommitted change); `BackgroundTaskManager.background_tasks`
growing without removal; `create_bot`'s read-then-write uniqueness TOCTOU (pre-existing).

## Friction in the skill

1. **`git diff --stat "$MB"` is dominated by lockfiles, and the scaling rule keys off "changed
   lines."** 1865 insertions read as "dispatch subagents" until you notice 1112 are
   `Cargo.lock`. The rule would be more useful phrased against reviewable lines, or with an
   explicit "exclude lockfiles/generated" step in Step 1.

2. **Step 1's ref loop worked exactly as advertised.** The comment about `&& … || …` printing
   two lines is a real trap and the loop avoided it. No issue.

3. **Severity-cap table vs. the rubric's HIGH clause collide on one finding.** The repeat-fire
   finding rests partly on doc language ("Fires when price *rises above*"), which Step 5 caps
   at MEDIUM. But the concrete, code-only fact is that *no mechanism for at-most-once delivery
   exists anywhere in the API*, which is a HIGH by the rubric. I resolved it by grounding the
   severity on the absent mechanism and flagging the conditional downgrade in the finding
   itself, but the skill doesn't say how to handle a finding with two sources at different caps.

4. **`references/output-contract.md` human template has no slot for "what I cut."** The
   severity rubric mandates saying what you cut "in the Coverage line," but the human-mode
   markdown template has no Coverage line — only "Angles run." I folded it into that section.

5. **Step 7's approval loop is unimplementable for a non-interactive agent** and the skill
   knows it only for subagent mode. Standalone-but-non-interactive (this run) falls between
   the two branches. I emitted the diff and wrote nothing, which is the safe reading.

6. **`references/memory-protocol.md` "Where it lives" step 3 says "ask the user once"** — same
   gap. I proposed the repo location with the tradeoff stated rather than picking one.

7. Minor: the skill references `../deep-code-review/references/severity-rubric.md` with a
   relative path that only resolves if `deep-code-review` is a sibling directory. It was here,
   but that's a fragile link for a skill distributed on its own.

## Constraint compliance

`git status --porcelain` in ninniku at start and finish: identical
(` M Cargo.lock`, ` M Cargo.toml`, ` M src/bot/alert_bot.rs`). No writes, no git state changes,
no `.claude/knowledge/` created. Nothing under either skill's `meta/` was read.
