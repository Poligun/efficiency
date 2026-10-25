# Experiment: orchestrator on sonnet-5-5-medium, run 2026-10-25 on the merged PR 49 head (7d97e49)

Produced by a reviewer agent; kept verbatim as evidence.

# Review: PR #49 (head 7d97e49) → origin/main (merge-base 4188b48)

PR #49 makes every deploy gate, in each package's working tree, the overrides on shared or unknown-sharing hashes of the characters whose outfit slots the package fills. Gating is a recorded change tagged `generated: Gate{outfits}`, with stale-gate drop and redo when the slots change. It also adds a persisted `$phaethon_promoted` switch written by profile switch, and it moves the `Gates` type from `check.rs` into a new `inspect/gate.rs`. Nothing blocks the merge. The one logic defect is latent and depends on a future registry change, and the design notes are mostly about the persisted format and naming.

**Coverage.** Aspects that ran: `code_api` (strong), `logic` (strong), `convention` (weak). `wire_api` was inactive because the script found no wire contract, route or CLI changes. Shape was `standard`, with 22 files and 1350 code lines. Neither the skill's step 3 convention ledger nor the haiku verifier pass was run as the skill specifies. I gave the convention scout a short ledger built from sibling files without counting occurrences, so its checks are unmeasured. The `surface-consistency` agent (A5) was skipped, since the two API aspects were not both strong. No finding went through a separate verifier agent. Instead I checked BLR-1 and A1 first-hand against the code, and A2 to A4 and the convention items are stamped unverified. Business-logic memory proposals were returned but not written, and I did not resolve a knowledge-base location. The `scope_detect.py` base was reported as `origin/HEAD`, and its merge-base matched the one `git merge-base origin/main HEAD` gave. Round 2 did not fire. Tests and docs were excluded by the scope script and read only for context.

## Needs a decision before merge
None. One open product question (Q-1) is under Could not resolve.

## Findings

### F1 — Phaethon's own detection section can be re-gated after a registry update (MEDIUM · SCOPED · plausible, latent)
`rust/phaethon/library/gate.rs:259` · committed

Redeploy idempotence rests on `Gates::of` (`inspect/gate.rs:168`) counting an assignment as a gate only when its section's hash is not shared in the current registry. The `[TextureOverridePhaethonDetect…]` sections that phaethon adds are not recognized as phaethon's own. Suppose a registry update reclassifies a detection hash from `outfit` to `partial` or `unknown`, and `outfit_blend` still finds a second blend for that outfit (Belle Basic has body and legs).

On the next deploy the old detection section returns from `ungated()` and is wrapped in `if $phaethon_promoted == 1 || $counter > 0`, so it can only set a counter that is already above 0. A second section with the same name is also appended, because `statements()` checks only the namespace peers for an existing `$counter = 2` and never the document itself. The loader drops that duplicate. Every gated override for the outfit then stays off unless the package is promoted. Nothing triggers this today.

```
let open = ungated(&found, knowledge)
} else if hash.as_deref().is_some_and(|hash| !shared(hash)) {
```

**Fix.** Treat an assignment to a `phaethon_*_outfit` counter as a gate whatever its hash, and exclude `TextureOverridePhaethonDetect*` sections from `ungated()`. As a smaller guard, make `statements()` check the document itself for an existing `$counter = 2` or a same-named section before adding a detection section.

### F2 — `Generated::Gate` persists `Vec<Slot>`, a type wider than the data (MEDIUM · SCOPED · grounded)
`rust/phaethon/library/change.rs:50` · committed

The list of gated outfits is written to `changes.json` as the general `Slot` enum, which also has non-outfit variants that can never appear here. Readers filter them (`gate_locked` with `matches!`, `describe` with a `_ => None` arm). Staleness is decided by comparing whole vectors (`outfits != slots`), so it depends on the write-time sort and dedup and on the derived `Ord`. This is a persisted format, so narrowing it to `(character, outfit)` pairs or comparing as sets later needs a migration, and doing it now costs nothing.

```
outfits: Vec<Slot>,
&& gate_outfits(entry).is_some_and(|outfits| outfits != slots)
```

**Fix.** Store `Vec<(String, String)>` or a dedicated `OutfitSlot` type and compare as sets.

## Design notes
(all unverified, unranked)
- `inspect/check.rs:630`: the `shared-ungated` check keeps its own loop beside the new public `ungated()`. The two differ on purpose (documented in `agents/inspection.md`), but the shader exclusion and gate test now live in two places and can drift.
- `inspect/gate.rs:55`: `Detector` stores `hash` and `outfit` that duplicate `resource.hash` and `resource.outfits[0]`, in a public serializable struct.
- `library/gate.rs:30`: `Gated` and `LeftUngated` describe packages, while the imported `Ungated` describes one override section. The pair reads as opposites at one level.
- Convention scout (unverified, LOW): `inspect/gate.rs:142` (`Gates::of`) and `:210` (`Gates::gated`) are `pub(crate)` without `///` docs. The three `Outcome` fields at `library/gate.rs:71-73` have none either, and fields are borderline. Test wiring, the `//!` module docs and `Error::io` use follow the sibling files.

## Could not resolve
- Q-1 (product intent): if package P is promoted and a non-promoted package Q, for another outfit of the same character, overrides the same hair hash, both overrides fire while Q's outfit is drawn and the loader's same-hash rule decides. The gate condition gives P no way to yield. The code cannot settle whether that is acceptable, so the owner must say.

Traced clean by the logic agent: stale-gate drop and restore ordering, refusal before any write and undo on partial failure; line-insertion index arithmetic including end-of-file cases; namespace-peer deduplication; keeping `PROMOTED` out of `read_values`, `sync` and `set`, and writing it as 1 or 0 from the profile at switch; and deploy gating only after every tree is built.

---
Review run statistics:
- Wall-clock: about 11 minutes after scope detection began. The first line of the block that measured it was lost to a failed `python3` call; the business-logic subagent itself ran about 10.8 minutes.
- Subagents dispatched: 3. Two on opus (code-api reviewer, business-logic-review) and one on haiku (convention scout). No verifier, round-2 or A5 agents.
- Skipped or not run as specified: separate verifier agents (Step 5); the measured convention ledger (Step 3); A1 wire reviewer (inactive aspect); A5 surface-consistency (not strong on both API aspects); knowledge-base location resolution and memory writes (read-only run); Step 8 posting (the PR is merged and posting was forbidden). `python3` was not on PATH, so I ran the scope script with `python`.
