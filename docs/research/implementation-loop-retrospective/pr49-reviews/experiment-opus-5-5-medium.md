# Experiment: orchestrator on opus-5-5-medium, run 2026-10-25 on the merged PR 49 head (7d97e49)

Produced by a reviewer agent; kept verbatim as evidence.

# Review: PR #49 (7d97e49) → origin/main (merge base 4188b48)

PR #49 makes every deploy gate a package's shared-hash overrides as a recorded change, and the core holds up. Redeploys and trees rebuilt from the record are idempotent, all plans are computed before any write, stale-gate reverts follow the per-file earliest-entry rule, and the promotion value never edits the tree. The one finding worth acting on is that the detector search looks only inside the INI being edited. A package whose body override sits in a different INI from its shared overrides therefore gets a second section on its own body blend hash, and the loader runs only one of the two.

**Coverage.**
- **Code API:** reviewed (A2, opus); the scope script rated it strong.
- **Business logic:** reviewed (A3, opus, `business-logic-review` in subagent mode); rated strong.
- **Conventions:** reviewed for the two new modules (A4, haiku). The script rated this aspect weak, and I built the ledger from measured probes.
- **Wire API:** not reviewed, because the script found no wire contract, route or CLI change.
- **Surface-consistency agent (A5):** not run, because its trigger needs both API aspects to be strong.
- **Verification:** I checked the one MEDIUM finding myself against the code and the repo's recipe and loader docs instead of dispatching a verifier. The LOW findings are unverified.
- **Round 2:** not triggered.
- **Knowledge base:** none exists, and this was a non-interactive run, so A3 proposed entries and nothing was written.

## Findings

### F1: Detection section duplicates the package's own body hash (MEDIUM · scoped · confirmed)
`rust/phaethon/library/gate.rs:399`

`plan()` accepts a detector only when it is in the INI being edited. `add_gates` edits only INIs that hold ungated overrides. When a package keeps its body override (the natural detector) in `body.ini` and its shared hair overrides in `hair.ini`, `hair.ini` has no detector of its own, so the code falls through to `knowledge.outfit_blend`. That function prefers the body blend, the same hash `body.ini` already overrides. The namespace peer check at line 637 does not prevent this, because it skips the section only when a peer already holds `$counter = 2`, and an unedited `body.ini` never receives that line.

The recipe adds a detection section only "If the mod does not override the outfit's body", which is a condition on the whole mod. `docs/zzmi-mod-anatomy.md:140` says that two sections on one hash conflict unless each sets `match_priority`, and that 3DMigoto then runs only the higher-priority one. The package's own body section usually sets no priority. That leaves two outcomes:
- If the body section runs, the detection section never sets the counter, and every gated part stays hidden unless the package is promoted.
- If the detection section runs, the mod's body mesh does not draw.

No test covers this case: `inis_of_one_namespace_share_one_counter` gates only hair sections in both INIs.

```rust
            let mut own = known
                .iter()
                .filter(|held| {
                    held.file == file && &held.character == character && &held.outfit == outfit
                })
```

**Fix.** When the INIs share a namespace, use the peer's detector instead: add the peer to the edited set and give it the `= 2` mark. Without a namespace, each INI has its own variables, so refuse with a `left_ungated` reason when another INI of the package overrides the `outfit_blend` hash. Add a test with the body override in one INI and the shared overrides in another.

### F2: `outfit_blend` does not require a hash that only one character lists (LOW · mechanical · unverified) · **latent** until a registry file lists an outfit-only blend hash under two characters
`rust/phaethon/inspect/knowledge.rs:321`

`detectors` and `ungated` take a hash only when exactly one registry entry lists it (`let [entry] = knowledge.lookup(&hash) else`, `inspect/gate.rs:118`). `outfit_blend` filters by character but does not check that only one character lists the hash. The two halves of one gate therefore disagree about what "ties to that outfit alone" means. If a blend hash were ever listed under two characters, the added detection section would set the counter while the other character is drawn. A2 checked that none of the three multi-character hashes in `data/hashes/3.2.0` is an outfit-only blend.

```rust
                entry.character == character
                    && entry.resource.sharing == Sharing::Outfit
                    && entry.resource.outfits == [outfit]
                    && entry.resource.is_blend()
```

**Fix.** Also require that `knowledge.lookup(&entry.resource.hash)` returns exactly one entry.

### F3: The saved gate record's `outfits` field can hold non-outfit slots (LOW · scoped · unverified)
`rust/phaethon/library/change.rs:50`

`Generated::Gate.outfits` is typed `Vec<Slot>`, so the saved change record accepts a `shared` slot, or any later variant, in a list documented as outfit slots. The writer filters to outfits first (`gate.rs:110`). The stale test compares that list with the outfit-filtered slots (`gate.rs:147`), so a non-outfit slot written by hand or by a future writer makes the entry compare stale on every deploy. `describe` (`gate.rs:362-365`) drops such slots without a message. Narrowing the type later means migrating records already on disk.

```rust
        outfits: Vec<Slot>,
```

**Fix.** Store character and outfit pairs, or a dedicated outfit type, before records accumulate.

## Design notes

These are opinions:
- `add_gates` and `plan`/`apply` report refusals as `String` inside `Result<Result<_, String>, Error>`. A4 raised this as a break from the crate's `Error` convention, but the strings are refusal reasons that become `LeftUngated.reason`, which matches how `Blocked.reason: String` is built in `deploy.rs:260`. The nested `Result` reads awkwardly, and a small refusal type would name the intent. It is not a convention violation.
- `rebind.rs` now holds `replace` and `restore`, which `gate.rs` also uses as general atomic-write helpers. A shared write module would sit better than a rebind module.
- `Detector` stores `hash` and `outfit`, which duplicate `resource.hash` and `resource.outfits[0]`.

## Convention ledger (measured)

| Rule | Support | Counterexamples | Verdict | PR #49 |
|---|---|---|---|---|
| A sibling `<module>_test.rs` file is attached with `#[path]` | 15 | 0 | established | followed |
| A `//!` doc comment opens each module | 23/23 | 0 | established | followed |
| A method that assumes the lock is held is a `pub(crate) fn *_locked` | 8 | 0 | established | followed |
| Result structs derive `Debug, Clone, PartialEq, Eq, Serialize` | 32 | 3 | established | followed |
| Modules are private (`mod x;`) and re-exported with `pub use` | 20 | 0 | established | followed |

Proposed knowledge entries from A3, none written:
- `INV-deploy-gating-001`: idempotency depends on `inspect::Gates` recognizing phaethon's own counter, which is set in a section on a non-shared hash.
- `INV-deploy-gating-002`: a stale-gate drop restores each file to the `before` blob of the earliest stale entry.

A3 checked and refuted these suspects:
- Multi-INI partial failure.
- Case handling of namespaces.
- Collisions between counter names.
- `$phaethon_promoted` handling in sync, set and switch.
- Insertion ordering.

---
**Run facts.**
- **Wall-clock time:** about 7 minutes (12:43 to 12:50).
- **Subagents:** 3. A2 code-api-reviewer and A3 business-logic-review ran on opus, and A4 convention-scout ran on haiku.
- **Skipped or substituted steps:**
  - `python3` was not found, so the scope script ran through `py -3`.
  - The Step 5 verifier was not dispatched; I verified the one MEDIUM finding inline.
  - A1 (wire) and A5 (surface consistency) did not run, because their triggers were not met.
  - Round 2 was not triggered.
  - Step 8 (posting) was skipped as instructed.
  - The knowledge base was not created, because the run was non-interactive.
