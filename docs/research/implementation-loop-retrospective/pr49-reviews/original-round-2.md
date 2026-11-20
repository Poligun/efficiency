# Original review round 2 of PR 49 (session 0e5c87c2, 18:11:33 UTC, orchestrator on Opus 5.5 medium)

Produced by a reviewer agent during the implementation loop; kept verbatim as evidence.

I ran the deep-code-review on PR #49 (task/gate-shared-overrides, `4188b48..b78efe4`, 22 files, about +1680/−120). Its verdict is mergeable: it found one MEDIUM bug and two LOW findings, and nothing blocks the merge. The core gating mechanics held up when traced:
- insertion ordering when several lines go in at one index;
- line endings at end of file;
- the `if` placed before `hash =` (3DMigoto pulls `hash`, `match_priority` and similar keys out before it parses the command list, so the `if` does not make the hash conditional);
- idempotency on redeploy and on a tree rebuilt from the record;
- undo on a failed write or record;
- the promotion value reaching `d3dx_user.ini` during `switch`;
- the refactor of the `check.rs` shared-ungated check, which behaves as before.

**Coverage.** These parts ran:
- **Business logic:** a dispatched Opus agent following the business-logic-review skill. I re-read the anchors for its three findings myself.
- **Code API and conventions:** reviewed inline by me.

These parts did not run:
- **Wire API:** the scope script found no wire contract in the diff.
- **Formal verifier pass:** skipped. I checked the cited lines against the current tree directly, so the "verified" labels below are my reading, not a separate verifier.
- **Knowledge base:** the repo has none, so nothing was written. The logic agent proposed two entries for a future `domains/deploy-gating.md`.

No files were modified, nothing was committed or pushed, and nothing was posted to the PR.

## Findings

### F1: INIs that share one `namespace =` each add a decrement of the same counter (MEDIUM · scoped fix · confirmed by code)
`rust/phaethon/library/gate.rs:538` (also `:497`)
```rust
if !holds(document, 0..document.lines().len(), &step) {
...
if !declares(document, name) {
```
- **What is wrong:** the plan, the declarations and the `[Present]` decrement are built one INI at a time. The "already there" checks (`holds`, `declares`) search only that one file, and neither `library/gate.rs` nor `inspect/gate.rs` mentions `namespace`. 3DMigoto names a global `$\<namespace>\<var>` (`IniHandler.cpp:284-289`), and every `[Present]` runs each frame.
- **Failure scenario:** take a package with `Body.ini` and `Hair.ini`, both declaring `namespace = BelleX`, both holding gated Belle overrides.
  - Each file declares `global $phaethon_belle_outfit` and `global persist $phaethon_promoted`, which produces a "Redeclaration" warning.
  - Each file also adds its own decrement, so the counter drops by 2 per frame instead of 1. The body draw sets it to 2, the two decrements take it to 0, and on the next frame the hair, which draws before the body, reads 0 and is skipped.
  - The result is that the mod's own hair vanishes on its own outfit, because the margin that the value of 2 provides is gone.
  - When both files need an added detection section, the second `[TextureOverridePhaethonDetectBelleBasic]` is also a duplicate section name.
- **Fix:** group INIs by `declared_namespace` and emit the declarations and the decrement once per namespace, or give the counter a name unique to each file.

### F2: Dropping a stale gate is refused because of an edit the restore would keep (LOW · mechanical fix · confirmed by code)
`rust/phaethon/library/gate.rs:171-176`
```rust
let after_first = entries
    .iter()
    .skip_while(|entry| entry.id != first.id)
    .skip(1)
```
- **What is wrong:** each file is restored to the `before` of the earliest stale gate on that file (`:167`). The "a later change edits it" refusal, however, scans every applied entry after the earliest stale gate overall.
- **Failure scenario:**
  1. Gate #1 (Belle Basic) edits `a.ini`.
  2. Rebind #2 edits `b.ini`.
  3. An updated embedded registry makes the next deploy record gate #3 (still Basic) on `b.ini`.
  4. The owner moves the package to Summer. The drop is refused ("change 2 edits b.ini after it"), although #3's `before` already contains #2. The package stays gated to Basic, so its parts show only on an outfit it no longer fills.
- **Fix:** for each restored file, check only the entries after the earliest stale entry that touched that file.

### F3: A bare `deploy` does not reset a promotion value an earlier `switch` wrote (LOW · needs decision · doc and code disagree)
`rust/phaethon/library/state.rs:813` and `agents/deploy.md:75`
```rust
.any(|active| active.family == placed.family && active.promoted);
```
- **What is wrong:** only `write_values` (`switch` and `set`) writes `$phaethon_promoted`. `agents/deploy.md:75` says "A bare `deploy` writes no value, so the default, gated, holds", but a `= 1` line left by an earlier switch stays in `d3dx_user.ini`, and the loader reads that file last.
- **Failure scenario:** switch to a profile that promotes package P, then run `phaethon deploy P`, then press F10. The gate stays lifted, which contradicts the doc.
- **Open question:** should a bare deploy write 0 for each gated INI, or should the doc say it keeps the value the last switch wrote?

## Design notes (opinions, unranked)
- `record_locked(..., generated: Option<(Generated, Vec<Slot>)>)` (`change.rs:193`) puts gate-only data into the generic record call. A second generated kind would need its own payload in that tuple; making the payload a variant of `Generated`, such as `Gate { outfits }`, would scale better.
- `Change.outfits` (`change.rs:42`) has the type `Vec<Slot>` but is named for one slot kind; `slots` would match `Library::slots`.
- The two crates each have a `gate.rs` (`inspect::gate`, `library::gate`) with different roles. That is acceptable, but grep results get ambiguous.
- `Gated.sections` counts every overridden section across all characters, while the GUI line (`characters_page.rs`) says "gated to its outfit" in the singular. For a package with several characters or outfits the log line is imprecise.

## Open intent question (from the logic agent)
When the only detector a file has for an outfit is an override that is not a blend buffer (the "then any" fallback in `agents/deploy.md`), does it fire on every frame that outfit is drawn? If it does not, the counter can lapse and gated parts flicker on the mod's own outfit.

Relevant files:
- `C:\Github\phaethon\rust\phaethon\library\gate.rs`
- `C:\Github\phaethon\rust\phaethon\library\state.rs`
- `C:\Github\phaethon\rust\phaethon\library\change.rs`
- `C:\Github\phaethon\agents\deploy.md`
