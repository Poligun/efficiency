# Ground truth — ninniku `cel-alert`

Standing eval target. Rust + protobuf, CEL-based price alerting.
Base `origin/HEAD` (main) → merge-base `e85ca8d9`. ~20 files, +1865/-507, of which
~1215 lines in source/wire files. `scope_detect.py` classifies it as `shape: standard`
with all four aspects `active` + `strong`.

**Every claim below was verified first-hand** by reading the code at the cited line, not
taken from an agent's report. Where a claim turned out weaker than initially believed,
that's recorded rather than quietly dropped — see [Corrections](#corrections).

The branch has uncommitted working-tree changes, which is part of what makes it a good
fixture: a review that only reads `main...HEAD` misses them.

---

## Must find

These are the assertions. A review that misses several of them is underperforming
regardless of how good its prose is.

| # | Finding | Anchor | Aspect | Verified |
|---|---|---|---|---|
| G1 | **Unvalidated strings reach expression source.** Caller-supplied symbol and decimal strings are interpolated into CEL *source text*, which is then compiled. `validate_alert_definition` checks field presence only. **See the severity caveat below — assert the defect, not the "injection" framing.** | `src/alert/mod.rs:32,41,51,55,61,67…` — 12 `format!` sites building CEL | logic (A7 taint) | ✅ read |
| G2 | **`DeleteAlert` can never succeed.** `create_alert` always calls `start_bot`; `delete_alert` calls `delete_bot` directly; `delete_bot` rejects any bot in `Running`. Nothing sends a stop first. | `src/server/mod.rs:667` calls `delete_bot`; `src/bot/bot_manager.rs:191` rejects Running | logic (A1 lifecycle) | ✅ read both |
| G3 | **No dedup, cooldown, or edge detection anywhere.** An alert re-fires every interval for as long as its condition holds. | `rg 'cooldown\|dedup\|last_fired\|already_fired\|debounce' src/ proto/` → **0 hits** | logic (A2) | ✅ grep = 0 |
| G4 | **Silent fallbacks invert trigger semantics.** `decimal()` parse failure returns `0.0`, making `price >= threshold` always true. Price conversion failures return `0.0`, making `fall_below` always true. `reduce_bars` returns `f64::NAN`. | `alert_engine.rs:33` (warn + 0.0), `:55,:59,:85` (`unwrap_or(0.0)`), `:116` (`f64::NAN`) | logic (A4) | ✅ read |
| G5 | **Declared-but-unwired surface.** `market_hours_filter` → 0 hits in `src/`. `required_symbols` → 0 hits. `initial_state` → 1 hit (written as `None`, never read). | `alert.proto` declares all three | logic (A6) / API honesty | ✅ grepped each |
| G6 | **Unrelated breaking proto change.** `pattern_day_trader = 7` and `daytrade_count = 21` removed via `reserved` in `account_info.proto` — a source-breaking change to every generated client, unrelated to alerting, riding in a feature branch. | `proto/…/alpaca/account_info.proto` | wire_api + scope | ✅ in diff |
| G7 | **Unchecked `i32` arithmetic on caller input**, plus a silent unit fallthrough: unknown `time_unit` maps to `MINUTE`, so `"DAY"` is wrong by 1440×. | `src/alert/mod.rs:206-213` | logic (A8) | ✅ read |

### Structural assertions

- Every finding carries severity, fix-clarity, an anchor `file:line` **that exists**, and
  quoted evidence.
- Ordering follows the rubric; CRITICAL/HIGH + NEEDS-DECISION pinned first.
- A Coverage line states which aspects ran and any caps hit.
- Total findings ≤ ~15.

---

## Must NOT find

These are traps. Each is a plausible-looking finding that the codebase itself contradicts,
and they're the more discriminating half of the eval — anyone can find bugs in this branch,
but a reviewer that files these has a precision problem that will cost it trust.

| Trap | Why it's wrong | Evidence |
|---|---|---|
| **"Module lists should be alphabetized"** | `src/bot/mod.rs` and `src/postgres/mod.rs` alphabetize; `src/alpaca/mod.rs` does **not** (`broker, alpaca_market_data, bar, …`). Ledger verdict: `mixed` → note at most, never a finding. | verified all three |
| **"`src/alert/` has no tests"** | The entire repo has **2** test modules (`src/alpaca/quote.rs`, `src/postgres/fetch_history.rs`). No testing convention exists to violate. Ledger verdict: `absent`. | `grep -rln 'cfg(test)' src/` |
| **Clippy / rustfmt findings** | `.cursor/rules/rust_rules.mdc` — the repo's only written convention doc — instructs the author to run `cargo clippy`, `cargo fix`, and `cargo fmt` before wrapping up. Citing a rule the repo already automates is noise. | read the rules file |
| **"`reserved 7` is a breaking change"** | `reserved` is the *correct* ritual for removing a field. The finding is the removal and its client impact (G6), never the keyword. | — |
| **Pre-existing issues on untouched lines** | Out of scope unless the branch newly makes them reachable. | — |

---

## Corrections

Recorded because the next iteration will otherwise re-derive them.

- **G1's severity framing was wrong, and an eval run made the better argument.** I recorded
  it as CRITICAL "expression injection." The iteration-1 with-skill run downgraded it to
  MEDIUM after establishing that `NativeTrigger.expression` already accepts *arbitrary CEL*
  from the same caller on the same RPC by design — so interpolating through `BuiltInTrigger`
  crosses no privilege boundary. It also read the CEL sandbox and confirmed only six
  registered functions plus the stdlib are reachable.

  That reasoning is correct and mine wasn't. The unvalidated interpolation is a real
  **correctness** defect (a symbol containing a quote produces a malformed or wrong
  expression) but not a privilege escalation.

  **The assertion is therefore about the defect, not the severity.** A review that reports
  the interpolation and argues the escalation question either way has passed G1; one that
  cries CRITICAL injection without checking whether a boundary is crossed has found the
  right line for the wrong reason. Note that the *baseline* runs mostly made the
  unexamined-CRITICAL call.

- **"private `mod x;` + `pub use x::Type;` is established 12:2."** Reported by an
  exploration agent; **does not hold**. Actual counts across `src/*/mod.rs`: 12 `pub use`
  lines against 10 `pub mod` lines. That's a ratio well under 3:1, so the establishment
  test says `mixed`, not `established` — which means `pub mod alert_bot;` is **not** a
  clean finding either. Treat it as a legitimate design note at most.

  This is the single most useful entry in this file: an agent reported a convention with
  confident counts, the counts were wrong, and the establishment test is what catches that
  class of error. It's also a reminder to verify subagent numbers rather than relaying them.

- **`code_lines` is ~1215, not ~791** as estimated during planning. The estimate excluded
  wire-contract lines; the script counts them. Either way the shape is `standard`, well
  under the `deep` threshold, so nothing downstream changes.

## Plausible but unverified

Reported by exploration agents, **not** confirmed first-hand. Do not use as assertions —
promote only after reading the code.

- Time-window gap between per-trigger `now` and a later `last_eval_time`.
- Positional `Vec<Option<Struct>>` trigger state misaligning after reorder (note: the
  update RPC is unimplemented, so this is latent rather than live — a good graveyard test
  case, since the refutation's guard is exactly `UpdateAlert` being unimplemented).
- Whole-alert abort when one trigger errors (`?` propagation).
- `build.rs` dropping serde derives from the whole bot proto package.
- Asymmetric CRUD: create returns the only handle, no read or list operation exists.
- Stray debug `info!` in the uncommitted changes to `src/bot/alert_bot.rs`.
- Broadcast channel lag making a bot permanently unstoppable.
