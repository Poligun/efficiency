# Original review round 3 of PR 49 (session 0e5c87c2, 18:21:15 UTC, orchestrator on Opus 5.5 medium)

Produced by a reviewer agent during the implementation loop; kept verbatim as evidence.

# Review: task/gate-shared-overrides → main (PR #49)

The branch makes every deploy gate the overrides on shared or unknown-sharing hashes in each package that fills an outfit slot, records that edit as a `generated: gate` change entry, and lifts the gate through a persisted `$phaethon_promoted` value that `switch` writes. One finding would change the plan before merge. When a mod's INIs share a namespace, the INI that relies on a peer's detection section is gated again on every later deploy, so the documented rule that a redeploy finds nothing to gate does not hold. The second finding is a persisted-schema shape that is cheap to fix now and costly once records exist on disk.

**Coverage.** Three aspects ran:
- Business logic ran as a fresh-context opus subagent using `business-logic-review` in subagent mode.
- Code API ran as an opus subagent.
- Conventions ran inline, because the aspect was weak and covered only two new files.

Wire API did not run, because the scope script found no wire contract, route or CLI change. I confirmed F1 myself by reading `Gates::of` and `gated` in `inspect/gate.rs` and `plan`/`statements` in `library/gate.rs`, and by tracing the fixture through two deploys. No separate verifier agents ran. F2 is grounded against in-repo precedent, and F3 is unverified. No knowledge base exists for this repo. The logic agent proposed two entries (an idempotency invariant and a note that the `insert` ordering is safe), and nothing was written. No files were modified, and nothing was committed, pushed or commented.

## Findings

### F1: A namespace peer without its own detector is re-gated on every redeploy (HIGH · scoped · confirmed)
`rust/phaethon/library/gate.rs:628` (with `rust/phaethon/inspect/gate.rs:182-190`)

**What is wrong.** Among INIs that share a namespace, `statements` skips the detection section when a peer already sets the counter:

```
        if peers
            .iter()
            .any(|held| holds(held, 0..held.lines().len(), &mark))
        {
            continue;
```

The second INI is still wrapped in `if $phaethon_promoted == 1 || $phaethon_belle_outfit > 0`. However, `Gates::of`, which `ungated` uses to decide what still needs a gate, collects counter-setting variables per file and ignores namespaces:

```
                .insert(ini.path.clone(), set.difference(&reset).cloned().collect());
...
            self.variables.get(file),
```

The second INI's wrapped sections test a variable that no section in their own file sets, so `gated()` returns false and they count as ungated again.

**Failure scenario.** Take the fixture from `inis_of_one_namespace_share_one_counter`: a.ini and b.ini both declare `namespace = BelleX`, they hold Belle hair overrides on `aa9ffb85` and `76a50b18`, and the slots are set to Belle Basic.
1. Deploy 1 gives a.ini the declarations, the decrement, `[TextureOverridePhaethonDetectBelleBasic]` and a wrap. b.ini gets only the wrap.
2. On deploy 2, `ungated` returns b.ini's section again. The unrecorded-edit check passes, the peers satisfy the declarations, decrement and detection, and `plan.wraps` adds a second nested `if … endif` around the body.
3. A new `generated: gate` entry is recorded, and `deployment.gated` is non-empty.

Every later deploy repeats this. The tree linked into `Mods` gets edited each time, the change record grows, and the rule in `agents/deploy.md` ("already there … a redeploy … finds nothing to gate") is broken. Inspection's `shared-ungated` also reports b.ini's sections as false positives. In-game behaviour stays correct, because the nested conditions are identical. The existing test deploys only once, so it does not catch the repeat.

**Fix.** Make `Gates::of` namespace-aware by merging `variables` across INIs that declare the same namespace before calling `gated`. That also removes the inspection false positive. Then add a second deploy to the namespace test and assert that it gates nothing.

### F2: The gate-only `outfits` is a top-level `Change` field instead of data on `Generated::Gate` (MEDIUM · scoped · grounded)
`rust/phaethon/library/change.rs:42`

**What is wrong.**
- The persisted change record stores `outfits: Vec<Slot>` next to `generated: Option<Generated>`, but the field means something only when `generated == Some(Gate)`.
- The code already pairs the two values: `record_locked` takes `Option<(Generated, Vec<Slot>)>` (`gate.rs:325`), and the only reader tests both together (`gate.rs:146-148`). The type then splits them again.
- The schema can therefore express meaningless states: `outfits` without `generated`, or a later variant that inherits a gate-only field. `Vec<Slot>` also admits `Shared` and `Global` slots, which a gate never detects.

**Failure scenario.** Carry-forward (#20) adds a second `Generated` variant with its own parameters. That variant needs another optional top-level field, so every reader must know which sibling field belongs to which variant. The alternative is folding the data into the variant at that point, which is a format migration of every `changes.json` that deploys have already written.

**Fix.** Use `enum Generated { Gate { outfits: Vec<Slot> } }` with `#[serde(tag = "kind", rename_all = "snake_case")]`. `Slot` in `state.rs:30` already follows this pattern. Have `record_locked` take `Option<Generated>`, and update `agents/changes.md` and the ADR 0003 amendment to match. This is cheapest before merge, while no record holds the current shape.

### F3: The PR description names an API that does not exist (LOW · mechanical · unverified)
The body says "`Document::insert_line` is new", but the method added at `rust/phaethon/ini/ini.rs:284` is `insert_line_before`. Correct the PR text.

## Design notes
- In the convention ledger, test placement is mixed: 15 files use `#[path = "*_test.rs"]` and 12 use inline `mod tests`. The new files' choice is not a finding.
- `drop_stale_gates` and `add_gates` return `Result<Result<_, String>, Error>`, which nothing else in the repo does. It works, but a named refusal type would read more clearly. This is an opinion.

## Could not resolve
- `docs/zzmi-mod-anatomy.md:140` says that when two overrides share a hash with `match_priority`, 3DMigoto "runs the higher priority section". If only one section runs, the added `match_priority = 0` detection section might never fire beside another mod that overrides the same body blend, such as a Belle Basic body mod. In that case the gated package would never show. The recipe says instead that the line "lets the section coexist". This was not introduced by the branch. The pending in-game check, or `IniHandler.cpp`'s duplicate-hash handling, would settle it: run a gated hair-only mod beside a body mod on the same outfit.

Checked and found sound:
- The ordering of `insert` (a stable sort, and an `endif` index can never equal another section's `if` index).
- The ordering in stale-gate drops (entries are kept in id order).
- The handling of `PROMOTED` in switch, set and sync, including namespaced line keys.
- The exact `[outfit]` match in `outfit_blend`.
- `insert_line_before` at the end of the file.
- Counter-name collisions (none among the registry characters).
- A `hash` line inside the `if` wrap, which the original mod already does.
