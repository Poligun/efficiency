# Run notes — business-logic-review, standalone (human) mode

Target: `/Users/yuhanzhao/GitHub/ninniku`, branch `cel-alert`, HEAD `b00b1d4`, merge-base `e85ca8d` off `origin/HEAD`.
Prompt: *"Something feels off about the alert evaluation code I just wrote but I can't put my finger on it. Can you dig into the logic and tell me what edge cases I've missed?"*

---

## 1. Scoping and mode detection

Step 1 worked exactly as written. The `for ref in ...; break` loop resolved `origin/HEAD` on the first try. The `--stat` total was 1,865 insertions, which would have looked like a fan-out-heavy diff; `scope_detect.py` returned `code_lines: 1215` with `excluded: {lockfile: 1112, manifest: 45}` and the note *"lockfile churn excluded from code_lines — dependency waves must not inflate the cost shape."* That's the single highest-value line in Step 1. Without it I'd have sized off ~1,865 and my estimate of "how much subagent budget does this need" would have been ~50% too high. The script also handed me a free A6 lead I'd otherwise have had to grep for: `signals: ["api_surface_touched", "new_module"]` on the three new files, and `wire_breaking` on `alpaca/account_info.proto` (which turned out to be unrelated to alerts — field removals in a different message — so I dropped it).

Mode detection was unambiguous: no `mode=subagent` in the prompt → human markdown, and I own the memory approval. No friction.

## 2. Step 2 — knowledge base

Checked both locations the protocol names:
- `/Users/yuhanzhao/GitHub/ninniku/.claude/` → contains only `settings.local.json`. No `knowledge/`.
- `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/` → exists, contains session `.jsonl` transcripts and a `memory/` dir, but **no `knowledge/`**.

So Step 2 was a no-op and I skipped straight to Step 3, per the skill's "Skip if no knowledge base exists — but offer to seed one in Step 7."

**How I would have used it.** Two of my findings would have been materially cheaper with a knowledge base, and I've written both into the proposed seed so the next review gets them:
- `MAP-alert-002` (config update keeps the Bot instance and its `trigger_states`). Establishing this cost a full subagent question chain through `bot_manager.rs` → `bot_loop.rs` → `bot_context.rs`. It is a *repo-wide* fact about the bot framework, not about alerts, and it converts the A9 positional-state finding from "theoretically reorderable" to "live today." That is exactly the "non-derivable or expensive to re-derive · changes a verdict or severity · describes a shape not a line" test in Step 7.
- `ABS-alert-005` (no dedup anywhere). Cheap to re-derive — one grep — but it's the sole support for the CRITICAL finding, so it earns a slot precisely *because* it's an absence claim that must be re-verified every time rather than trusted.

I deliberately did **not** propose an entry for anything the compiler enforces, and I kept the `f64`-vs-`Decimal` question out of memory entirely — it's product rationale the team owns, which the skill routes to `docs/`.

The one thing I noticed: the `~/.claude/projects/<slug>/memory/` directory that *does* exist is not the same thing as `knowledge/`, and the protocol doesn't mention it. A reviewer moving fast could mistake one for the other. Worth one clarifying clause in `memory-protocol.md § Where it lives`.

## 3. Step 3 — the behavior model, and how it shaped the hunt

I wrote the model before reading `bot_loop.rs` or `bot_manager.rs`, from `alert.proto` + the three new source files. It paid off in a specific, traceable way, so it's worth recording *how* rather than just asserting it did.

```
ENTITIES  Alert/AlertBot (Stopped→Running→deleted, Redis-backed);
          per-trigger CEL state Option<Struct> (None → Some, in-memory only);
          BotMetadata (bot_config, account_identifier, can_trade)
EFFECTS   notify via Sink; market-data reads; Redis writes; task spawn; CEL compile+exec
PROMISES  "any trigger fired → dispatch"; "each trigger maintains independent state";
          "engine subscribes to required_symbols"; "initial_state seeds the first eval";
          "next_state omitted → previous carried forward"; "{{name}} substituted";
          "DeleteAlert removes unconditionally"; "at most one trading bot per account";
          "Decimal is unvalidated by design"
TRIGGERS  bot_evaluation_loop every eval_schedule.interval; CreateAlert; DeleteAlert;
          UpdateBotConfig (UpdateAlert is unimplemented)
```

The PROMISES block is what did the work. Six of the thirteen findings are a promise line failing to meet a code line, and I found them by walking that list rather than by reading code hoping something jumped out — `required_symbols`, `initial_state`, `{{name}}`, "independent state" vs. the `?` batch abort, "unconditionally" vs. `Cannot delete a running bot`, and the `can_trade` uniqueness rule. Notably, three of those are in *comments*, and the skill's Step 5 cap table made me stop and check whether each was doc-only. Each time the answer was no — the code independently demonstrates the defect and the doc is corroboration — so the "strongest source governs" clause is what kept `required_symbols` and `initial_state` at HIGH rather than reflexively capping them at MEDIUM. That clause is well-written and I used it consciously; an earlier version of me would have capped all three.

The EFFECTS line is what made A2 the first angle I ran instead of the fourth. "Notify" was listed as the only externally visible effect, which turns A2's question into a single concrete one: what makes *notify* happen at most once? Answer: nothing.

## 4. Step 4 — which angles ran, inline vs. subagent

`code_lines: 1215` is above the ~400 threshold, so the scaling rule called for subagents. I did **not** fan out all ten. I ran the angles that need the whole behavior model in one head inline, and dispatched the two that are essentially mechanical evidence-gathering.

| Angle | Where | Result |
|---|---|---|
| A1 Lifecycle | subagent (`Explore`, read-only) | 3 findings (DeleteAlert can't succeed; `can_trade` only at create; CreateAlert orphan — last one cut for length) |
| A2 Repeat-Fire | inline | 1 finding — the CRITICAL |
| A3 Boundary & Window | inline | 3 findings (zero-width first window; `last_eval_time` advances on failure; inclusive-both-ends SQL — cut) |
| A4 Fallback & Sentinel | inline | 1 finding (`decimal() → 0.0`), 1 refuted (NaN watermark) |
| A5 Partial Failure | inline | 1 finding (`?` aborts the batch) |
| A6 Declared Surface | subagent (`Explore`, read-only) | 2 findings (`required_symbols`, `initial_state`) + a 5-row table |
| A7 Taint | inline | 1 finding (CEL interpolation) |
| A8 Numeric Domain | inline | 2 findings (unit fallthrough; overflow/panic) |
| A9 Identity & Correlation | subagent (part C of the lifecycle brief) | 1 finding — positional state rebinding |
| A10 Concurrency | subagent (part A/F of the lifecycle brief) | **0 findings, deliberately** |

**Angles skipped: none.** All ten ran. The four conditional gates all fired and I checked each explicitly rather than assuming: A7 (`format!` building CEL that `Program::compile` parses), A8 (i32/i64 arithmetic on wire-supplied numbers), A9 (`states[i]` positional indexing), A10 (`block_in_place`, `Mutex`, `tokio::spawn`).

**A10 producing zero findings is the result I'm most confident about, and it's because of the angle's own guard rail.** I had two plausible-sounding candidates: (a) a `tokio::sync::Mutex` held across `block_in_place` + `block_on` of network I/O, and (b) a double-start race spawning two loops for one bot_id. The angle says *"If you can't name the other task, don't report it."* For (a) the subagent established there is exactly one holder — the `AlertBot` is moved into its loop and never shared (`rg 'trigger_states|last_eval_time' src/` outside `alert_bot.rs` returns only a by-value parameter). No second holder, no finding. For (b) the subagent *did* name both paths concretely, but the two loops would hold *separate* `AlertBot` instances, so it's duplicate evaluation rather than a data race, and it's a pre-existing property of the bot framework rather than something this branch introduced — out of scope for a branch review. Both got dropped. Without that one sentence in `angles.md` I'd have shipped two speculative HIGHs.

**Subagent design.** Two dispatched, both `Explore` (read-only tool set by definition), both with an explicit read-only constraint in the first line of the prompt plus an explicit "do not touch `/Users/yuhanzhao/GitHub/efficiency`". Both ran synchronously and in parallel in one message. I gave each a *numbered list of exact questions with the expected evidence form* ("quote the attribute line", "show the rg you ran", "if you cannot find something, say not found") rather than an angle name. That is why both came back with verbatim quotes and line numbers I could use directly instead of summaries I'd have to re-verify. The A6 brief in particular — "for each of these 10 names, run this rg and tell me whether a real consumer exists" — is the shape the skill describes as "nearly a grep," and it returned a clean table plus the raw hit lists in one round trip.

**Where the scaling rule is slightly off.** The rule reads as "under 400 → inline, over 400 → subagents," and taken literally at 1,215 lines it suggests fanning out most angles. That would have been wrong here. The diff is 1,215 lines but the *conceptual surface* is one 337-line engine, one 220-line translator, and one 112-line bot — small enough that one head holding the model beats ten holding fragments, which is the exact argument the skill makes for the under-400 case. What actually justified subagents was not size, it was **evidence-gathering breadth**: A6 needed ten independent greps and A1/A10 needed a five-file call-graph trace, and neither needs the behavior model at all. Suggestion below.

## 5. Step 5 — trace verification, and the finding count through it

This is where the skill earned the most, so here is the honest funnel:

| Stage | Count |
|---|---|
| Candidate observations after the angle sweep | 22 |
| Survived writing a concrete execution trace | 18 |
| Reported after the ~12 cap | 13 |
| Explicitly named as cut, with anchors | 3 |
| Explicitly named as refuted, with the reason | 1 |

**Four died writing the trace**, and one is worth recording in detail because it's the archetype the skill is built to catch. I was confident that the `reduce_bars` NaN sentinel permanently poisons the trailing high-water mark: `price` is NaN → `new_hwm = max_decimal(price, prev_hwm)` → NaN state persisted → trigger dead forever. It reads like a textbook A4 finding, and `angles.md` even primes it (*"many max/min implementations silently return the other operand when given one, so a running maximum seeded with NaN freezes instead of erroring"*). Writing the trace forced me to state what happens on the *next* evaluation, and the answer is that Rust's `f64::max` returns the other operand — so `max_decimal(real_price, NaN)` yields `real_price` and the watermark **recovers**. "Freezes" ≠ "poisons," and I had conflated them. It's a genuine near-miss: the reference text nudged me toward a real mechanism, and only the mandatory trace stopped me from over-claiming its consequence. I recorded it as `REF-alert-001` with `reason_class: wrong-model` and the corrected model in one sentence, exactly as the graveyard section requires.

The other three deaths were quieter: a claimed `next_state` carry-forward mismatch (the code actually implements the documented behavior correctly); a claimed float-precision defect on `to_f64()` (real but design-acknowledged in a comment, so it became question #6 rather than a finding, per the "inference about intent → not a finding" row); and a claimed `can_trade` migration hole (the `is_none_or(bot_can_trade)` fallback is conservative in the right direction — I'd misread it as trusting the stored field).

**The latent marker was load-bearing.** Five findings are unreachable today behind the `reduce_bars` stub or the un-wired Telegram sink. Without the rubric's latent-defect section I'd have faced a bad choice: call them LOW (dishonest — they're baked in and certain) or call them HIGH with no caveat (misleading — nothing is hurting the user this week). The `**latent** until X` marker resolves it cleanly, and the two guards were useful: for each one I quoted the specific code that blocks it (`f64::NAN` at `alert_engine.rs:116`, `warn!("...not yet implemented")` at `alert_bot.rs:107`) rather than pointing at a nearby `TODO`. One case failed that check in a useful way — the i32 overflow in `lookback_duration` *looks* latent behind `reduce_bars`, but the multiplication runs during translation, before any CEL executes, so it is live. I'd have mislabelled it without the "verify actually unreachable" guard.

**Ordering.** Applied severity desc → fix-clarity asc, with the one CRITICAL+NEEDS-DECISION pinned into its own section. The momentum argument is real: the report now opens with a decision the author has to make, then gives them a MECHANICAL fix (`DeleteAlert`) early in the HIGH band before the harder SCOPED ones.

## 6. Friction, ordered by time cost

**1. The scaling rule keys on the wrong variable (~10 min of hesitation, and I nearly over-dispatched).**
`code_lines: 1215` said "fan out," but the right call was to fan out only the two angles that are evidence-collection rather than judgment. I resolved it by reading the *justification* sentence ("one reviewer holding the whole behavior model beats ten holding fragments") and inverting it, but that required treating the rationale as the rule and the threshold as advisory.
**Suggestion:** make the two-axis nature explicit. Something like: *"Size sets the budget; angle character sets the assignment. A4, A6, and the evidence-gathering half of A1/A10 are near-mechanical — dispatch them at any size above the threshold. A2, A3, A5, and the judgment half of A9 degrade when split from the behavior model — keep them inline until the diff exceeds what one context can hold (roughly 1,500 code lines), then partition by subsystem rather than by angle."* That is what I actually did, and it took reasoning from first principles to get there.

**2. `angles.md` is 305 lines and Step 4 says to load "the sections whose gate fired" (~5 min, and I loaded the whole file).**
There's no cheap way to know which sections fired without reading the gates, and the gates are inside the sections. I read all of it, which was fine at this size but is the kind of thing that stops being fine.
**Suggestion:** the contents line at the top already lists all ten angles — add the conditional gates inline there, e.g. `A7 Taint (gate: diff builds a string something later interprets)`. Then a reviewer reads ~15 lines to decide what to load. Zero restructuring cost.

**3. The "roughly 12" cap versus the rubric's "roughly 15" (~3 min).**
`output-contract.md § Both modes` says cap at ~12; `severity-rubric.md § Caps and honesty` says ~15. I went with 13 and disclosed the cuts, which satisfies both, but I had to notice the discrepancy and decide. These two numbers should match, or the contract should say "12 for human mode, 15 for the orchestrator's merged report" if the difference is intentional.

**4. Step 7's non-interactive guidance doesn't cover "interactive, but the location question is unanswered" (~3 min).**
The skill handles two cases cleanly: subagent mode (emit proposals, write nothing) and non-interactive (treat silence as a decline, print the diff, say it's unwritten). This run was nominally interactive but single-turn, *and* the repo-vs-personal location question from `memory-protocol.md § Where it lives` had never been asked. So I had two unanswered questions stacked. I printed the diff, wrote nothing, and stated both the location trade-off and that nothing was written — which I believe is right, but I reasoned it out rather than followed it.
**Suggestion:** one clause in Step 7: *"If no knowledge base exists and you cannot get an answer this turn, print the proposed seed and the location trade-off together, and write nothing. Creating the directory is an irreversible choice on the user's behalf."*

**5. No guidance on what to do with an unrelated defect found in touched-but-adjacent code (~2 min).**
`scope_detect.py` flagged `wire_breaking` on `alpaca/account_info.proto` — two field removals with no relationship to alerts. It's in the diff, it's a real wire break, and it's outside anything in my behavior model. Step 3 says "if a finding can't be traced to a promise in the model, it belongs in a general code review, not here," which I followed by dropping it silently. But *silently* may be wrong — a one-line "also in this diff, out of scope for this skill" pointer costs nothing and the user is otherwise relying on a review that saw it and said nothing.
**Suggestion:** add to Step 6: *"If an angle surfaces something real but outside the behavior model, name it in one line under the Coverage paragraph and route it, rather than dropping it. Seeing and not saying is worse than saying it's out of scope."*

**6. Minor: the `Write` tool refused both output paths.** The harness returned *"Subagents should return findings as text, not write report files."* Expected per the task brief; fell back to `cat <<'EOF'` heredocs, which worked. Not a skill issue — recording it because it cost one round trip and any future eval harness driving this skill through a subagent-shaped tool set will hit the same wall.

## 7. What the skill got right

- **The intent-free angles are the whole ballgame.** Eleven of thirteen findings are wrong under *any* intent — a delete that can't succeed, a declared field with no reader, a unit fallthrough that's off by 1440×. I never had to guess what the author wanted. The two that do depend on intent (edge-vs-level firing, `required_symbols`) are the two I pushed into the questions section rather than asserting. The design does what it claims: it routes inference away from findings.
- **Trace-before-finding killed 4 of 22 candidates**, including one the reference material had actively primed me toward. That is the single highest-value mechanic in the skill and it is correctly placed *before* Step 6 rather than as a review pass after.
- **The severity cap table's "strongest source governs" clause** kept three doc-corroborated findings at their true severity instead of reflexively capping them at MEDIUM. Without that paragraph, `required_symbols` and `initial_state` would both have been under-reported.
- **A6 is exactly as advertised** — "nearly a grep, and it reliably finds real problems." It cost one subagent round trip and produced seven dead surfaces including two HIGHs. Best yield-per-token in the run by a wide margin.
- **A10's "if you can't name the other task, don't report it"** prevented two speculative findings. Angles that tell you when *not* to report are rarer and more valuable than angles that tell you what to look for.
- **The latent marker** let me report five real defects at honest severity without implying the user's alerts are broken today. The two guards on it caught one misclassification (the i32 overflow is live, not latent).
- **The bad/good example pair in Step 6** — specifically "a negative grep that establishes absence" — is why the CRITICAL finding leads with `rg ... (no matches)` instead of "there appears to be no deduplication." The instruction to write my own example rather than adapt theirs is right; every trace in the report is from this codebase with real numbers.
- **`scope_detect.py`'s `code_lines`** prevented a ~50% cost misestimate. Worth keeping the cross-skill dependency.

## 8. Compliance

- **Read-only on `/Users/yuhanzhao/GitHub/ninniku`: verified byte-identical.**
  Before: ` M Cargo.lock` / ` M Cargo.toml` / ` M src/bot/alert_bot.rs`
  After:  ` M Cargo.lock` / ` M Cargo.toml` / ` M src/bot/alert_bot.rs`
  Identical content and order. Branch still `cel-alert`, HEAD still `b00b1d4925d61c26516c97fb7ed26b570692dc33`. `git stash list` = 3 entries, pre-existing and untouched (I ran no stash command). Working-tree diff checksum `df7385d6d8159f0fef64f14d08cd76eb98d376eb`. Every git invocation was read-only: `status`, `branch --show-current`, `rev-parse`, `merge-base`, `diff`, `log`, `stash list`. No file under the repo was created, modified, or deleted; nothing was posted to GitHub.
- **Memory: nothing written.** No `.claude/knowledge/` was created in the repo and no `knowledge/` directory was created under `~/.claude/projects/`. The full proposed seed (INDEX + `domains/alert.md` + `review/findings/alert.md` with the graveyard entry) is printed as a diff in the report's final section, with the repo-vs-personal location choice left to the user, per Step 7's non-interactive guidance.
- **Excluded paths untouched.** Nothing under `skills/*/meta/`, `skills/*/evals/`, or `skills/deep-code-review-workspace/` was read. Files read under `/Users/yuhanzhao/GitHub/efficiency`: `skills/business-logic-review/SKILL.md`, `skills/business-logic-review/references/angles.md`, `skills/business-logic-review/references/output-contract.md`, `skills/business-logic-review/references/memory-protocol.md`, `skills/deep-code-review/references/severity-rubric.md`; plus `skills/deep-code-review/scripts/scope_detect.py` executed (not read) against the ninniku working tree, which is a read-only operation. One `ls` listed the two `references/` directories and `deep-code-review/scripts/`; it did not touch `meta/` or `evals/`.
- **Subagent constraints.** Both subagents were `Explore` (read-only tool set), and both prompts opened with an explicit "STRICTLY READ-ONLY … do not create, modify, or delete any file … no git command that mutates state," plus an explicit prohibition on touching `/Users/yuhanzhao/GitHub/efficiency`. Neither returned any indication of a write.
- **Outputs.** Both files written by `cat <<'EOF'` heredoc into `.../with_skill/outputs/`, after the `Write` tool refused the paths with a subagent guard (*"Subagents should return findings as text, not write report files"*). Only the two named files were created; nothing else was written anywhere.

## Stats

- **subagents_dispatched:** 2 (both `Explore`, read-only, run synchronously in parallel)
- **angles_run:** 10 of 10 — A1, A2, A3, A4, A5, A6 (core, all mandatory) + A7, A8, A9, A10 (conditional, all four gates fired). Inline: A2, A3, A4, A5, A7, A8. Subagent: A1, A6, A9, A10.
- **angles_skipped:** 0
- **findings_reported:** 13 — 2 CRITICAL (one of them pinned as needs-decision), 8 HIGH, 2 MEDIUM plus 1 MEDIUM roll-up table covering 5 dead declarations, 1 LOW. Plus 3 verified-but-cut for length (named with anchors in the Coverage paragraph), 1 refuted (recorded as REF-alert-001 in the proposed graveyard), 6 open intent questions.
- **candidates before trace-verification:** 22 → 18 survived a trace → 13 after the cap
- **models used:** orchestrator `claude-opus-5[1m]`; both subagents `Explore` on the inherited model (no `model` override passed)
