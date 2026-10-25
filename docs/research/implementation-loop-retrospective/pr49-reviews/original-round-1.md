# Original review round 1 of PR 49 (session 0e5c87c2, 06:28:37 UTC, orchestrator on Opus 5.5 medium)

Produced by a reviewer agent during the implementation loop; kept verbatim as evidence.

I ran the deep-code-review skill on PR #49, `task/gate-shared-overrides` against main (merge base 4188b48, head 3206c6e). It found one HIGH, two MEDIUM and five LOW issues, and nothing CRITICAL. The HIGH one needs an owner decision: a gate is never redone when a package's slots change. Nothing was modified, committed, pushed or posted.

The branch makes every deploy gate a package's overrides on shared or unknown-sharing hashes. It edits the INIs in the package's working tree and records the edit as a change entry marked `generated: gate`, and a profile switch writes `$phaethon_promoted` into `d3dx_user.ini` as 1 or 0. In my read, the insertion and idempotency mechanics hold up. The gaps are in lifecycle, in partial failure, and in how inspection and the GUI report the result.

**Coverage.**
- **Ran:** code API review (opus), business-logic review (opus) and convention review (haiku).
- **Not run:** the wire-contract review, because the scope script found no wire, route or CLI contract changes.
- **Convention review:** it returned zero findings. The new modules follow the test-module, `_locked` and `map_err(Error::…)` patterns.
- **Verification:** I did not dispatch separate verifier agents. I checked each MEDIUM and HIGH finding by reading the cited code myself (deploy.rs 232–330, inspect/gate.rs, check.rs 640–700, rebind.rs 300–335, gui/characters_page.rs). The LOW findings are unverified.
- **Knowledge base:** none exists for this repo, so the logic reviewer's memory proposals were not written.
- **Not done:** no builds or tests were run.

## Needs a decision before merge

### F1: A gate is never redone when the package's slots change (HIGH, NEEDS-DECISION, confirmed)
`rust/phaethon/library/gate.rs:93` and `:104`, with `rust/phaethon/inspect/gate.rs:65`

`gate_locked` only ever adds gates, and it has two early returns:
```
if outfits.is_empty() {
    return Ok(None);
...
if open.is_empty() {
    return Ok(None);
```
`Gates::gated` treats a section as gated when it tests a variable that any non-shared override in the same INI sets. It does not check which outfit that detector belongs to.

**Failure scenario:**
1. A hair mod is set with `set_slots` to Belle/Basic and deployed. It gains `[TextureOverridePhaethonDetectBelleBasic]`, and its hair section is wrapped in `if $phaethon_promoted == 1 || $phaethon_belle_outfit > 0`.
2. The user then changes the slots, either with `set_slots(None)` (which puts it on the global list), to another Belle outfit, or to another character, and deploys again.
3. Each case returns `Ok(None)`. The global list hits `outfits.is_empty()`. For another Belle outfit, the old detector still sets the counter, so the section counts as gated. For another character, `open` is filtered to empty.
4. The mod keeps working only while Belle's Basic body is drawn, and neither `gated` nor `left_ungated` reports anything.

No API drops or reverts a generated change, so the user has no way out short of editing by hand.

**Open question:** should deploy record which slot set produced the gate and, when the slots differ, rebuild the INI without the gate entry and gate it again? Or should it report the package in `left_ungated`? A related question: should a user be able to decline the gate for one package?

## Findings

### F2: A failed deploy still leaves earlier packages' live trees gated (MEDIUM, SCOPED, confirmed)
`rust/phaethon/library/deploy.rs:240–243`, `:312`

The comment promises that a failed deploy changes nothing:
```
// Every working tree is built and gated before Mods is touched, so
// a package that cannot be materialized fails the deploy with
// nothing changed.
let wanted = self.wanted(active, &mut out)?;
```
However, `wanted()` materializes and then gates each package in turn (`match self.gate_locked(&place, knowledge, SystemTime::now())? {`). A later error stops the loop after earlier packages' INIs are already rewritten and recorded. Such errors include a missing blob in `materialize_locked`, a slug clash, or a gate I/O or record error. Those trees are already junctioned into `Mods`, so the edits are live.

**Failure scenario:** `switch(B)` runs where B holds P, which is promoted and already deployed but ungated from an older build, and Q, whose blob is missing.
1. P's tree is gated and recorded.
2. Q fails, so `switch` returns Err before `write_values` runs.
3. P now declares `global persist $phaethon_promoted = 0`, and `d3dx_user.ini` has no line for it.
4. After F10, P's promoted hair disappears from Belle's other outfits, while the switch reported failure.

**Fix:** materialize every tree first and gate in a second pass. Otherwise, correct the comment and the "Gating" rules in agents/deploy.md.

### F3: Inspection and deploy disagree on which overrides are ungated (MEDIUM, SCOPED, confirmed)
`rust/phaethon/inspect/gate.rs:4`, against `rust/phaethon/inspect/check.rs:654` and `:697`

The module doc says "Inspection reports the first as `shared-ungated`", but `check.rs` keeps its own loop, and the two rules differ in two ways:

| Case | `ungated()`, used by deploy | `check.rs`, used by inspect |
|---|---|---|
| `Sharing::Unknown` | gated (gate.rs:65) | not warned (`if resource.sharing.is_shared()`, check.rs:654) |
| Hash listed under several characters | skipped (`let [entry] = knowledge.lookup(&hash) else`) | warned |

The `unknown-sharing` note at check.rs:697 also tells the user that such overrides "are treated as belonging only to the outfits the registry lists". Deploy gates those same overrides.

**Consequences:**
- A mod with unknown-sharing overrides gets no warning from `inspect`, yet deploy rewrites its INIs.
- A hash listed under two characters gets a warning from `inspect`, yet deploy never gates it.

**Fix:** drive the `shared-ungated` warning from `gate::ungated()` or from one shared rule, and correct the note.

### F4: The GUI never shows `left_ungated` or `gated` (MEDIUM, MECHANICAL, confirmed)
`rust/phaethon/library/gate.rs:44` (`pub struct LeftUngated {`); the consumer is `rust/phaethon/gui/characters_page.rs:196–208`

The Characters page logs the deployed, removed and blocked counts, and the reason for each blocked package. It reads neither new field. In the GUI, a package refused gating looks like a clean deploy. The refusal reason "…has unrecorded edits: record or revert them, then deploy again" never reaches the user, and the clipping the gate exists to prevent ships anyway. The GUI file is outside the diff, but the new public type is what it ignores.

**Fix:** log the `left_ungated` reasons the same way the blocked reasons are logged.

### F5: `restore`'s error says "recording failed" when a file write failed (LOW, MECHANICAL, unverified)
`rust/phaethon/library/rebind.rs:329`
```
"recording failed ({error}), and {} could not be put back ({restore}); it stays edited and unrecorded",
```
The new caller `undo` (library/gate.rs:145) also runs when writing a second INI fails, before anything is recorded. The message then points the user at the change log. When several restores fail, the `fold` nests the "recording failed (…)" prefix once per file.

**Fix:** drop the stage wording, or let the caller pass it in.

### F6: "Detector" has two definitions in inspect/gate.rs (LOW, SCOPED, unverified)
`rust/phaethon/inspect/gate.rs:36` and `:126`

- The public `detectors()` requires `Sharing::Outfit` under one character.
- The private `Gates.detectors` accepts any hash for which `!shared(hash)` holds, which includes unknown-sharing and unlisted hashes.

So a mod's own variable set on an unknown-sharing hash counts as a gate, and deploy leaves that override ungated, even though the public rule would reject that hash as a detector.

**Fix:** rename the private field or unify the two rules.

### F7: `Document::insert_line` uses the opposite index rule to `insert_entry_after` (LOW, MECHANICAL, unverified)
`rust/phaethon/ini/ini.rs:283` (`pub fn insert_line(&mut self, index: usize, raw: &[u8]) {`)

`insert_entry_after` inserts after `index` and does nothing when the index is out of range. `insert_line` inserts before `index` and clamps an out-of-range index to the end. A wrong index therefore fails silently in opposite ways: the sibling drops the line, and the new method appends it to the end of the file, possibly inside the wrong section.

**Fix:** rename it `insert_line_before` and use one out-of-range rule for both methods.

### F8: The body-blend preference is coded in two crates (LOW, SCOPED, unverified)
`rust/phaethon/library/gate.rs:242` (`fn preference`), against `rust/phaethon/inspect/knowledge.rs:306`/`:331` (`outfit_blend`, `is_body`)

Both places parse the `|`-joined `kind` and `component` strings. A change such as a new body label updates one choice and not the other, so existing detector sections and added detection sections would key on different classes of hash.

**Fix:** expose `Resource::is_blend()` and `Resource::is_body()` once and call them from both places.

## Design notes

These are opinions, not defects:
- The public `Detector` (inspect/gate.rs:53) copies `hash`, `outfit` and `character` beside a `resource` that already holds them.
- `pub(crate)` `Gates::of` and `Gates::gated` have no doc comments. Doc-comment coverage across the repo is mixed, so this is not a finding.
- The logic reviewer asked a second question: when a package fills two outfits and one cannot be detected, should the whole package be left ungated, as now, or should only that outfit's detection be skipped? The current behaviour matches agents/deploy.md.

The logic reviewer checked and ruled out several suspects:
- **Insertion order in `insert()`:** the sort is stable, an `endif` and a following `if` never share an index, and a section can never be both wrapped and marked.
- **Idempotency:** an unchanged redeploy gates nothing.
- **Multi-INI mods:** each INI gets its own detection section and counter.
- **Namespaced INIs:** the `d3dx_user.ini` key for them is correct.
- **Record failure:** `undo` restores the files.
- **Left ungated:** a package left ungated still deploys.
