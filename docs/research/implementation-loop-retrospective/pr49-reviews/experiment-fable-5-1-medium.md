# Experiment: orchestrator on fable-5-1-medium, run 2026-10-25 on the merged PR 49 head (7d97e49)

Produced by a reviewer agent; kept verbatim as evidence.

# Review: PR #49 (7d97e49, `[#19] deploy: automatic gating of shared-hash overrides`) → origin/main (4188b48)

The branch makes every deploy apply the skin-detection gating recipe to each package that fills an outfit slot, as a recorded change made before `Mods` is touched, and lifts the gate at runtime through a persisted `$phaethon_promoted` that a profile switch writes. The design is coherent, the docs and ADR amendment match the code, and the new public surface follows its siblings. The one finding that should change the plan is a lifecycle gap: a gate that a later recorded edit (a rebind, or any `change record`) builds on can never be dropped once the package's slots move, and the refusal names an operation that does not exist yet.

**Coverage.** The scope script activated `code_api` (strong, 9 files), `logic` (strong, 1350 code lines) and `convention` (weak, 2 new files); `wire_api` was inactive because the diff has no wire contract, route or CLI change, so no wire reviewer ran, and the surface-consistency check did not run because only one API aspect was active. Three finders ran (code-api on opus, business-logic on opus, convention scout on haiku) and the three findings at MEDIUM or above each got a verifier on sonnet; the three LOW findings are stamped unverified. No round 2 fired. No knowledge base exists in the repo or the personal space, and this run was non-interactive, so the business-logic agent's three memory proposals (gate entry lifecycle, the idempotency invariant that rests on `Gates` recognising phaethon's own wrap, and the namespace-peer question) were not written anywhere; they are available on request. Nothing was posted to GitHub and nothing in the worktree was modified.

## Needs a decision before merge

### F1 — A stale gate under a later recorded edit can never be dropped (HIGH · needs-decision · confirmed)
`rust/phaethon/library/gate.rs:188`

`drop_stale_gates` refuses whenever an applied entry that is not itself a gate touches the INI after the stale gate, and the message tells the user to "drop or redo that change". No code path drops an entry: `Status::Dropped` is written only at `gate.rs:219`, the CLI offers `change list|pending|record` only (`cli.rs:463-465`), and `agents/changes.md:75` defers every status but `applied` to carry-forward (#20). Redoing the change, or hand-removing the gate and recording that, adds another applied entry after the gate, so the refusal repeats on every deploy and the package keeps detecting the outfit it no longer fills. The trigger is ordinary: deploy a mod with slots `[Belle Basic]`, rebind one key (`rebind.rs` records through `record_locked`), move the slots, deploy. `gate_test.rs:405` (`a_later_edit_keeps_a_stale_gate`) asserts exactly this refusal as intended, so the limitation is known, but the sibling message at line 195 ("record or revert them") steers the unrecorded-edit case straight into it. The verifier proposed MEDIUM because restoring the old slots or promoting the package are workarounds; I keep HIGH because the ADR amendment introduces the drop precisely so that "a hair mod moved between slots would otherwise stay limited to an outfit it no longer fills", and that is the outcome here on a path phaethon's own rebind command produces.

```
"the gate in {file} is for {gated_for}, not {}, and change {} edits {file} after it: drop or redo that change, then deploy again",
```

**Fix.** Decide how a stale gate under a later edit is lifted before #20 lands: strip phaethon's own gate lines (the `COMMENT`-tagged declarations, the `if $phaethon_promoted` wraps, the `PhaethonDetect` sections) in place and record that as a new entry, or ship a `change drop` ahead of #20, or accept the wait and say so. Whichever is chosen, the message at line 188 must name an operation that exists (today: put the slots back, or promote), and the message at line 195 should not recommend `record`, since recording leads into this state.

## Findings

### F2 — Planning ignores namespace peers' detectors (MEDIUM · scoped · plausible)
`rust/phaethon/library/gate.rs:399`

`plan` looks for a detector only in the INI being gated, although INIs of one `namespace` share the counter and `detectors()` already spans the whole mod. When the body-blend override lives in a peer INI that has nothing to gate (so it is never in `files`), the plan falls through to `Knowledge::outfit_blend` and appends a `[TextureOverridePhaethonDetect…]` section on the same hash the peer already overrides; the dedup at lines 637-641 only looks for an existing `$counter = 2` line, not for a detector on that hash. The mod then carries two `TextureOverride` sections on one hash in one namespace, which `agents/deploy.md:96` lists as unverified loader behaviour, and the output depends on the `BTreeSet` order of file names. Gating still works in that state because the added section sets the shared counter whenever the body is drawn, so the harm is the duplicate-hash section and the departure from the recipe, which marks the mod's own body section. The namespace test at `gate_test.rs:365` uses two hair-only INIs and does not cover a peer that holds the body override.

```
held.file == file && &held.character == character && &held.outfit == outfit
```

**Fix.** When the INI declares a namespace, include detectors from every INI of that namespace in `own` and place the mark in the peer's section; that peer then needs editing and recording even when it has nothing to gate, so `files` and the record paths must include it. Add the two-INI body-in-peer case to the namespace test.

### F3 — `inspect::check` and `inspect::gate` import each other (LOW · mechanical · unverified)
`rust/phaethon/inspect/gate.rs:17`

`Gates` moved into `gate.rs` but still needs `check::uses`, which the PR made `pub(crate)` for that purpose, while `check.rs:12` imports `Gates` from `gate.rs`. The lexical helpers `gate.rs` already uses (`text`, `override_hash`, `starts_with_ignore_case`) live in `attribute.rs`, which is where `uses` belongs; the cycle is harmless to the compiler but makes the two modules inseparable.

```
use crate::check::uses;
```

**Fix.** Move `uses` (and `declaration`, its pair) to `attribute.rs` and import it from there in both modules.

### F4 — `Detector` exposes `Resource` so `library` re-derives the ranking (LOW · scoped · unverified)
`rust/phaethon/inspect/gate.rs:56`

`Detector.resource` is public only so that `library/gate.rs:450` can rank detectors with its own `preference()`, which restates the "body blend first" rule that `Knowledge::outfit_blend` (`knowledge.rs:328`) already encodes. The field also duplicates `Detector.hash` and `Detector.outfit`. A change to the preference rule now has to be made in two crates.

```
pub resource: Resource,
```

**Fix.** Return detectors already ranked from `inspect`, or expose one ranking method on `Resource` and drop the duplicated `hash` and `outfit` fields.

## Design notes

- Gating is mandatory with no per-package or per-deploy opt-out (A2, verdict TASTE). This is the owner's documented decision (ADR 0003 amendment; `agents/deploy.md:65`), promotion is the designed lift, and an unrecorded hand edit leaves the package deployed ungated with a repeating refusal. It becomes a finding only if the `match_priority = 0` risk at `agents/deploy.md:96` is confirmed in game, at which point a hair-only package would have no route but promotion.
- `shared-ungated` in `check.rs:630-654` and `ungated()` in `inspect/gate.rs:68` select "ungated override" with different filters (attributed versus slot characters, multi-character hashes, `unknown` sharing); `agents/inspection.md` discloses the difference, but a later rule change has to be made twice, and a post-deploy inspection can still warn on hashes the deploy result neither gated nor listed as left ungated.
- `Generated::Gate { outfits: Vec<Slot> }` admits `Shared` and `Global` variants that the gate never stores, and the shape lands in `changes.json`, so narrowing it later needs a migration.
- `drop_stale_gates` and `add_gates` return `Result<Result<_, String>, Error>`, a shape used nowhere else in the repo; both are private and `gate_locked` flattens them into `Outcome`, so no caller sees it, but a named `Refused(String)` would read better.
- `Ungated` and `Detector` repeat `Override`'s file, section and hash fields (`attribute.rs:31`) and add `header`; embedding `Override` would keep one location type across the three public structs.
- Convention ledger: both new files follow every established rule (module `//!` docs, 23/23; result structs deriving `Debug, Clone, PartialEq, Eq, Serialize`, 45 against 3; `Error` variants at crate boundaries; no `unwrap` outside tests). Test placement (10 sibling `_test.rs` files against 12 inline `mod tests`), doc comments on every function and `#[must_use]` are mixed across the repo and produced no finding.

---

**Run summary.** Wall clock: about 16 minutes (12:43 to 12:59). Subagents dispatched: 6, in two rounds, one message each: round 1 A2 code-api (opus), A3 business-logic (opus), A4 convention scout (haiku); verification batch of 3 (all sonnet), one per MEDIUM-or-above finding. Steps skipped or adjusted: A1 wire-contract and A5 surface-consistency did not run because the scope script left `wire_api` inactive; round 2 did not fire; the knowledge-base location question (Step 4) was not asked because the run is non-interactive and neither location exists, so A3's memory proposals were returned, not written; Step 8 (posting to GitHub) was not run, as instructed. `python3` is not on PATH on this machine, so the scope script was run with the Python 3.13 interpreter at `C:\Users\Yuhan Zhao\AppData\Local\Programs\Python\Python313\python.exe` under `-I`. The worktree was not modified.
