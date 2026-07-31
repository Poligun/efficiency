# Run notes — deep-code-review on ninniku@cel-alert, narrowed to proto/API

User's framing: *"Just look at the proto changes on this branch — I want to know if the API
design is sound before other teams start building against it. Skip the implementation."*

## Aspects run vs. skipped

`scripts/scope_detect.py --pretty` exited 0 and reported `shape: standard`, all four aspects
active at `strength: strong`:

| Aspect | Script verdict | What I did | Why |
|---|---|---|---|
| `wire_api` | active / strong (5 proto files, `wire_breaking` in account_info.proto, build.rs touched) | **Ran** — A1 wire-contract-reviewer, opus | The only aspect the user asked about |
| `code_api` | active / strong (5 files changed exported surface, 3 new modules) | **Skipped** | User said skip the implementation; the Rust surface is implementation |
| `logic` | active / strong (1215 changed lines) | **Skipped** | Same. Also skipped the `business-logic-review` sibling-skill dispatch entirely |
| `convention` | active / strong (new `src/alert/` directory) | **Skipped** | All three convention files are `src/*.rs` |
| A5 surface-consistency | n/a | **Skipped** | Gate is "both API aspects strong"; `code_api` was skipped by the user |

Consequences of the narrowing that I handled deliberately:

- **Step 3 (convention ledger) was not built.** It only feeds A4, which didn't run. No time spent.
- **Knowledge-base resolution (Step 4) was not performed.** That step is gated on `logic` being
  active in the dispatch sense; since A3 never ran, there was no subagent to stall on the
  question, and asking the user would have been pure overhead. Worth noting the SKILL text ties
  this to "if `logic` is active" — which it *was*, per the script — rather than "if you're
  dispatching A3". I read the intent, not the letter. **This is a real ambiguity in the skill.**
- **I read `src/` heavily anyway**, per the "user asks for one aspect only" edge case. This was
  the single most valuable decision in the run: 6 of the 13 findings and both pinned decisions
  are contract-vs-implementation contradictions that are *invisible* from the proto alone
  (`required_symbols`, `initial_state`, `market_hours_filter`, `Sink` delivery, `{{binding}}`
  templating, the `reduce_bars` NaN stub). A literal reading of "skip the implementation" would
  have produced a near-clean bill of health on a contract that mostly doesn't work. Every finding
  is anchored in a `.proto` file; I filed nothing about implementation quality per se.

## Subagent count

**13 total.**

- 1 finder: A1 wire-contract-reviewer (opus, background). Returned 18 findings.
- 12 verifiers (sonnet, dispatched in 4 batches of 4/2/4/2 to respect the concurrency caution).
  All 12 returned. Verdicts: **12 GROUNDED, 0 TASTE, 0 REFUTED.**
  Two carried severity adjustments I accepted (`can_trade` HIGH→MEDIUM; `DeleteBot` bypass
  HIGH→MEDIUM); one I overrode (`time_unit`, verifier leaned MEDIUM, I kept HIGH because
  "nothing consumes it yet" is exactly the window the user asked about).
- Round 2: **not triggered.** No round-2 condition fired — nothing died for a shared reason, no
  HIGH needed a fact outside the diff that a verifier hadn't already been asked for, and the one
  strong aspect returned 18 findings rather than zero.

Verification cap: the skill caps verifiers at 12 and I hit it exactly. Three MEDIUM+ findings
went unverified (F4 UpdateAlert, F9 dead `Alert` message, F12 no read op) and are stamped as
such in the report. I read F4 and F9 first-hand, which is weaker than an adversarial check and
is disclosed as such.

## Findings pipeline

- A1 returned 18. I independently developed ~16 before A1 came back (Step 2/3 first-hand reading),
  which made arbitration real rather than rubber-stamping.
- Dedup collapsed 18 → 15: merged A1-1 (Sink never delivers) with A1-12 (templating never
  implemented) into one CRITICAL, since both are "Sink is declared and does nothing"; merged
  A1-4 with A1-13 (session-high drift became a design note under the same finding); dropped
  A1-17 (`interval` has no minimum) to design notes for the 15-finding cap, disclosed in Coverage.
- One finding is mine alone, not A1's: **F11, `DeleteBot` bypassing `DeleteAlert`'s account
  check.** A1 got adjacent to it (it flagged `GetBotStatuses` being unscoped) but missed the
  delete path. Arbitration value was real here.
- The `breakout NaN` verifier *widened* a finding — it found the `bar` Baseline variant also
  routes through the stub, which A1 had missed, so 3 of 6 baselines are dead rather than 2. I
  rewrote F6 accordingly.
- The `AccountInfo` verifier surfaced the best single detail in the report: the wire-breaking
  field removal lives in commit `aad07b3 "Bump dependnecies"`. Neither A1 nor I had checked which
  commit carried it.

## Friction in the skill

Ordered by how much time each cost.

1. **No way to block on a subagent.** This was the dominant friction. A1 (opus, background) took
   ~6.5 minutes; the harness only surfaces completion notifications between tool calls, so I had
   to invent filler work to receive them. I tried `Monitor` with an idle `sleep` loop, which was
   the wrong tool (it just idles and notifies on *its* schedule) and I had to `TaskStop` it. I
   then used a background `stat`-polling loop, which also isn't what either tool is for. The
   SKILL says "launch every active agent in a single message so they run concurrently" but says
   nothing about what the orchestrator does while they run. **Suggestion:** tell the orchestrator
   explicitly to continue Step 2/3 first-hand reading while round 1 is in flight — which is what
   I ended up doing productively, but only after wasting two tool calls on the wrong mechanism.

2. **Step 4's knowledge-base resolution is mis-gated.** "If `logic` is active, resolve where
   accumulated knowledge lives *before* dispatching" reads as keyed on the scope script's
   `aspects.logic.active`, but its stated purpose ("so no subagent stalls on a question it can't
   answer") only applies if you're actually dispatching A3. When the user narrows scope away from
   `logic`, the letter tells you to interrupt them with a directory question for no reason.
   **Suggestion:** re-key it to "if you are dispatching A3".

3. **The 12-verifier cap collides with a rich diff.** A1 alone returned 18 findings, 17 of them
   MEDIUM+. After dedup I had 15, so the cap forced three to ship unverified. That's the design
   working as intended and I disclosed it — but on a `strong`/`strong`/`strong`/`strong` diff the
   cap binds immediately, and the skill's own framing ("capped at 12; disclose in Coverage if you
   hit the cap") slightly undersells how routine hitting it will be. Not a bug, but the Coverage
   line is doing heavy lifting.

4. **Verifier severity adjustments have no arbitration rule.** Step 6 says severity disputes
   between *agents* are resolved by the orchestrator, but verifiers also propose
   `SEVERITY_ADJUSTMENT`, and the skill doesn't say whether that's advisory or binding. I treated
   it as advisory (accepted two, overrode one) and said so in the report. Worth one sentence in
   Step 5.

5. **Minor: `scripts/__pycache__/` is checked into the skill directory.** `scope_detect.cpython-314.pyc`
   sits next to the script. Harmless, but it's noise in a skill that's otherwise clean.

6. **Minor: the report template has no slot for "the user narrowed scope".** The Coverage line
   covers it, but "Which aspects ran and which didn't, with the reason" doesn't hint that
   *user-requested* skips should be distinguished from *script-inactive* skips. They read very
   differently to the author — one is "we didn't check" and the other is "you told us not to". I
   wrote it that way anyway; a template nudge would help.

## Things the skill got right that mattered here

- **Gating on measured scope, then honoring a user narrowing on top of it.** The edge case
  "read the narrowing as constraining where findings are anchored, not what you may read" is the
  single instruction that saved this review. Without it this would have been a 3-finding report
  about naming and enums.
- **The false-positive list did real work.** It pre-emptively killed the two findings I'd have
  otherwise filed on `reserved 7;` and on `pre_market` being unimplemented — and, more usefully,
  its "disclosure only in the implementation" carve-out is precisely the pattern that turned out
  to be this branch's dominant defect. Six findings hang off that one sentence.
- **Severity-as-impact with the "breaking change to fix later" clause.** Both pinned decisions
  (`time_unit`, firing semantics) are HIGH only because of that clause. Under a
  confidence-weighted scheme both would have been LOW notes and the review would have missed
  what the user actually asked.

## Compliance

Read-only honored. `git status --short` in `/Users/yuhanzhao/GitHub/ninniku` is byte-identical
before and after (`M Cargo.lock`, `M Cargo.toml`, `M src/bot/alert_bot.rs`); no files created,
no git state mutated, nothing posted to GitHub, Step 8 not offered. All 13 subagents were given
an explicit read-only constraint in their prompts. Nothing under the skill's `meta/` directory
was read or listed. Output files written via heredoc as instructed.
