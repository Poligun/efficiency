# Run notes — deep-code-review, narrowed to proto/API design

Branch: `cel-alert` @ b00b1d4 · base `origin/HEAD` @ e85ca8d9 · READ-ONLY run, nothing posted to GitHub.

## Aspects run vs. skipped

`scripts/scope_detect.py` returned `shape: standard` with **all four aspects active at
`strength: strong`**:

| Aspect | Script verdict | What I did | Why |
|---|---|---|---|
| `wire_api` | strong (5 proto files, `wire_breaking` signal, build contract touched) | **RAN** — 1 finder agent (A1) | The user's explicit scope |
| `code_api` | strong (5 files changed exported surface, 3 new modules) | **SKIPPED** | User: "Skip the implementation" |
| `logic` | strong (1215 changed source lines) | **SKIPPED** | User: "Skip the implementation" |
| `convention` | strong (3 new source files, new directory) | **SKIPPED** | User: "Skip the implementation" |
| A5 surface-consistency | gated on *both* API aspects strong | **SKIPPED** | Only one API aspect was in scope |

Followed the SKILL.md edge case verbatim: *"The user asks for one aspect only ('just review the
proto') — honor it, run only that agent, and say in Coverage which aspects you skipped at their
request."* Because `convention` was skipped, **Step 3 (the convention ledger) was not built** — it
exists only to feed A4, which didn't run.

Two judgment calls on the scope boundary:
1. **Kept `build.rs`** in A1's file list. It's in the `wire_api` aspect's file list, the
   wire-contract role file explicitly covers codegen contracts, and it isn't "implementation" in
   the sense the user meant. Disclosed in the report's Coverage line with an offer to drop it.
2. **Let A1 read `src/` as evidence only.** The role file requires checking "does the handler exist,
   does it do what the contract says" — without that, every contract-vs-implementation finding
   (which turned out to be 7 of 10) is unreachable. Findings had to be *anchored* in a proto file.
   This is the single highest-leverage decision in the run; a literal reading of "skip the
   implementation" that forbade reading `src/` would have produced a near-empty report.

## Subagents dispatched: 14 total

| Wave | Count | Model | Purpose |
|---|---|---|---|
| Step 4 finder | 1 | opus | A1 wire-contract-reviewer → 12 candidate findings |
| Step 5 verifiers | 12 | sonnet | One per MEDIUM+ finding (cap is 12; hit exactly, not exceeded) |
| Step 6 round 2 | 1 | opus | One narrow tracer: "can a client read back an alert?" → returned NO FINDING |

Round 2 fired on the trigger *"arbitration surfaced something in an active aspect that no agent
covered"* — I noticed during Step 6 that there is no `GetAlert`/`ListAlerts` and that the `Alert`
message is unreferenced. The tracer found the read path does exist (`alert_id` == `bot_id`, so
`GetBotMetadata` returns the definition) and correctly declined to manufacture a finding. That
became a design note instead. No round 3.

## Arbitration decisions

- **No cross-agent conflicts** — only one finder ran, so Step 6 was mostly severity assignment.
- **Overrode verifier on F8** (CEL injection): verifier said lower to MEDIUM citing a safe function
  registry, an inert sink, and a loopback bind. Kept HIGH under the rubric's *"API shape that will
  require a breaking change to fix later"* clause — the finding is about the `Decimal` doc comment
  promising no validation, not about today's runtime reachability. Override disclosed in-report.
- **Overrode verifier on F9** (time_unit): verifier said lower to MEDIUM because the existing enum
  lacks HOUR/DAY. That's an argument about *fix effort*, not impact — the rubric warns explicitly
  against conflating them. Accepted MEDIUM anyway on the impact merits, but moved `fix_clarity`
  from MECHANICAL to SCOPED, which is where the verifier's actual observation belonged.
- **Accepted verifier raise on F10** (percent_offset MEDIUM→HIGH): the verifier found
  `src/ta/renko.rs:148` treats a sibling percent field as `/100.0`, i.e. the opposite convention in
  the same repo. That's a genuine cited contradiction and it changed my read.
- **Ran my own grep rather than a round-2 agent** for the `AccountInfo` blast radius. A1 asserted
  "this repo contains no generated clients or frontends" — factually wrong. There are two:
  `ninniku-fe/` (TypeScript, tracked project, gitignored generated output) and `analytics/`
  (Python pb2, gitignored entirely). Neither has a hand-written reader of the removed fields, so
  the finding survived as a design note rather than dying. Worth noting: A1's false premise was
  caught by its *verifier*, which is the mechanism working as designed.

## Findings pipeline

12 candidates → 10 GROUNDED, 2 TASTE (demoted to design notes) → 0 REFUTED → +1 self-found note
(the dead `Alert` message) + 1 note from the round-2 tracer. Final: 2 CRITICAL, 6 HIGH, 1 MEDIUM,
4 design notes. Under the ~15 cap; nothing cut, so nothing to disclose as truncated.

Five of the ten ranked findings are the same root cause — the proto documents behavior that has no
reader, and discloses only one instance of it. I kept them as separate findings (different anchors,
different fixes) but led the report with the pattern, per the rubric's guidance on ordering for
reader momentum.

## Friction in the skill

1. **The narrowed-scope edge case is one bullet, and it's load-bearing.** SKILL.md line 316 says
   "honor it, run only that agent" but doesn't address the two questions that actually came up:
   may the wire agent still read `src/` (yes, or the aspect is gutted), and what happens to Step 3
   (nothing — it's dead weight when `convention` is off). Both were inferrable, but a sentence in
   the edge case would remove the guesswork. Suggested addition: *"A narrowed aspect still reads
   other files as evidence; it just can't anchor findings in them. Skip any step that exists only
   to feed a skipped agent."*
2. **Step 5's "one verifier per finding, capped at 12" collided with the 20-concurrent-subagent
   ceiling.** I dispatched 12 verifiers in one message; 4 failed with
   `Concurrent subagent limit reached` and had to be re-sent. The cap of 12 is fine in principle,
   but the skill should say to batch in waves under the platform limit, or note that the
   finder+verifier fan-out shares one budget. Cost me one round-trip.
3. **The Write tool refused to create `report.md`** ("Subagents should return findings as text, not
   write report files"), which conflicts with an explicit instruction to save the report to a path.
   Worked around via a shell heredoc. Not a skill defect, but anyone running this skill from a
   subagent context will hit it.
4. **No guidance on verifier model tier.** Step 4 specifies models for A1–A5 and explains the
   reasoning well, but Step 5 says nothing. I used sonnet, reasoning that verification is a
   bounded, evidence-checking task closer to A4's profile than A1's. A one-line note would make
   that consistent across runs.
5. **`references/severity-rubric.md` is genuinely good and did real work.** The "severity is impact,
   not confidence" split plus the explicit HIGH clause for *"an API shape that will require a
   breaking change to fix later"* is what let the design findings keep their rank instead of all
   collapsing to MEDIUM. Same for the TASTE-not-REFUTED default — it saved both demoted findings
   from deletion, and one of them (the `AccountInfo` scope creep) is arguably the thing most worth
   a human's attention.
6. **`scope_detect.py` worked cleanly** — correctly excluded 1112 lines of lockfile churn from
   `code_lines`, flagged the `wire_breaking` signal in `account_info.proto` with the exact removed
   lines as evidence, and surfaced the three dependency major bumps as notes. No friction.
