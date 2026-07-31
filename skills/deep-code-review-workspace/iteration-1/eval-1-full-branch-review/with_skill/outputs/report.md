# Review: cel-alert → origin/HEAD

This branch adds a user-configurable price-alert feature: a new `poligun.ninniku.alert` proto package, three RPCs, a CEL translation/evaluation engine under `src/alert/`, and an `AlertBot` that reuses the existing Bot/BotManager machinery. The design is sound in outline — reusing the bot lifecycle for alerts is a good call, and the `BuiltInTrigger → NativeTrigger` translation is a clean layering choice. **My overall read is that this is not ready to merge as a working feature**: as it stands, an alert on a US equity can never fire, an alert on anything can never notify, and an alert can never be deleted. Several of those are known-incomplete by the author's own comments, but the *contract* discloses almost none of it, so a client generating against this proto will build against promises the code doesn't keep.

**Coverage.** All four aspects ran at `strength: strong` — wire contracts (5 proto files + `build.rs`), code API (5 files), business logic (18 files), conventions (3 new files), plus a surface-consistency pass. Five finder agents, twelve verifiers (the cap — verification ran on the highest-severity unique findings; the rest are stamped `unverified` below), and one round-2 tracer. Three gaps to name: **(1)** I merged four separate "declared field with no reader" findings into F10 and cut three low-value items to Design notes to stay near the 15-finding cap — nothing above MEDIUM was cut. **(2)** The round-2 tracer's finding (D1) was not independently re-verified by a separate agent, since the verifier cap was already spent; I read its load-bearing lines myself instead and confirmed them. **(3)** No accumulated-knowledge base exists for this repo and this run was non-interactive, so the business-logic agent *proposed* memory rather than writing it — see "Proposed memory" at the end. Nothing in the working tree was modified.

---

## Needs a decision before merge

### D1 — Alerts on non-crypto symbols accept, start, and then never fire (CRITICAL · needs-decision · confirmed)
`proto/poligun/ninniku/alert/alert.proto:80`

`BuiltInTrigger.symbol` is a bare string with no asset-class field and no crypto note anywhere in the file, and `validate_alert_definition` performs no symbol validation. But market data reaches alerts only through a Postgres cache with no live-API fallback, and the only writers to that cache are pinned to Alpaca's crypto endpoints. So `latest_quote("AAPL")` returns `Ok(None)` forever, which becomes an `ExecutionError`, which aborts the whole alert every cycle — while `CreateAlert` returned 200 and started a bot. The crypto-only data plane is pre-existing; what's new is that every other surface *discloses* it (`Subscribe` returns `unimplemented` for non-crypto) and this one silently accepts.

```
// proto/poligun/ninniku/alert/alert.proto:80
message BuiltInTrigger {
  string symbol = 1;
```
```rust
// src/server/mod.rs:429-432
if subscriptions.iter().any(|s| s.asset_class != AssetClass::Crypto as i32) {
    return Err(Status::unimplemented("Only crypto subscriptions are supported"));
}
```

I verified the write side is closed by construction: one `MarketData` impl (`src/alpaca/alpaca_market_data.rs:19`), three tables with one `batch_upsert` each, six call sites, all in `crypto_ws.rs` / `crypto.rs`, both pinned to `/v1beta3/crypto/us`.

**Open question.** Is the alert feature intended to be crypto-only for now, or is equity support expected to land alongside it? If crypto-only, `validate_alert_definition` should reject non-crypto symbols with the same `unimplemented` message `Subscribe` uses, and the proto should say so. If equities are in scope, this branch depends on an equity ingestion path that doesn't exist yet.

### D2 — Trigger state is RAM-only, so every restart resets trailing watermarks (HIGH · needs-decision · confirmed)
`src/bot/alert_bot.rs:21`

`trigger_states` lives only in the `AlertBot` struct. Nothing writes `TriggerResult.next_state` back to Redis, and the resume path builds a fresh bot with all-`None` state. Absent state, `prev_hwm` falls back to the *current price*. A `trailing_below AAPL price_offset 5.00` that has ridden 200 → 250 is armed at 245; a deploy while AAPL is at 240 silently re-seeds the watermark to 240 and re-arms at 235. The alert gave up 10 points of trail and the user gets no signal. This is precisely the scenario a trailing stop exists to survive.

```rust
// src/bot/alert_bot.rs:19-24
pub(super) fn new(trigger_count: usize) -> Self {
    Self {
        trigger_states: Mutex::new(vec![None; trigger_count]),
        last_eval_time: Mutex::new(None),
    }
}
```
```
// proto/poligun/ninniku/alert/alert.proto:20
// State to persist and pass to the next evaluation as context.state.
```

**Open question.** Is trigger state meant to survive a restart? If yes it needs a persistence path plus a staleness policy for long outages. If no, the proto comment should say "per-process" and the `water_mark` docs should warn that the trail resets — right now the contract says "persist" and nothing does.

---

## Findings

### F1 — Telegram delivery is a no-op while `sink` is mandatory (CRITICAL · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:209`

The contract describes `message_template` with `{{name}}` substitution and override semantics and discloses nothing about it being incomplete — while the *same file* explicitly marks `pre_market`/`post_market` "Not yet implemented", which makes the omission read as a promise. `validate_alert_definition` makes `sink` required. The implementation formats the message and throws it at a log. There is no Telegram client anywhere in the repo and no `{{}}` substitution logic anywhere.

```rust
// src/bot/alert_bot.rs:105-107
// TODO: deliver via Telegram when Sink support is wired up
info!("AlertBot: trigger {} fired — {}", i, message);
warn!("AlertBot: Telegram notification not yet implemented");
```

A user configures an alert, gets a success response and a running bot, and receives nothing when the market moves.

**Fix.** Either wire up delivery, or disclose it in the proto the way `pre_market` is disclosed. The `{{name}}` substitution needs to ship with delivery or users will receive literal braces.

### F2 — Five documented trigger surfaces can never fire (`reduce_bars` stub) (CRITICAL · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:87`

Three of six `Baseline` variants (`high`, `low`, `bar` — the last covering all six OHLCV fields) and two of six trigger types (`BreakoutAbove`, `BreakoutBelow`) all translate to `reduce_bars`, which is a stub. None carries a not-implemented marker, unlike `pre_market` in the same file, and `validate_alert_definition` rejects none of them. Naming the internal function in a comment (`// session high via reduce_bars`) documents *mechanism*, not implementation status — an API consumer can't tell the field is inert.

```rust
// src/alert/alert_engine.rs:98-99
// --- reduce_bars: stub — bar range queries not yet in MarketData trait.
//     Returns sentinel values so breakout triggers silently never fire.
```

The implementation comment also understates its own scope: it says "breakout triggers", but *every* trigger type is dead when the baseline is `high`/`low`/`bar`.

**Fix.** Reject these five variants in `validate_alert_definition` with a clear `unimplemented`, and mark them in the proto — or implement `reduce_bars`. Note `Bar::get_highest_high` (`src/postgres/bar.rs:200`) looks like the start of that backend but has zero callers.

### F3 — An unparseable `Decimal` becomes 0.0, firing the alert immediately (HIGH · mechanical · confirmed)
`src/alert/alert_engine.rs:31`

Every BuiltInTrigger threshold flows through `decimal()`, which swallows parse failure into `0.0`. `Decimal.value` is a raw string the API documents as unvalidated, and `validate_alert_definition` never inspects it. A client sending `" 200"` — a copy-pasted price with a leading space, which Rust's `f64` parser does *not* trim (verified empirically) — produces `price >= 0.0`, so the alert fires on its very first evaluation and every cycle after. `FallBelow` with the same typo becomes permanently silent instead.

```rust
// src/alert/alert_engine.rs:31-36
ctx.add_function("decimal", |s: Arc<String>| -> f64 {
    s.parse::<f64>().unwrap_or_else(|_| {
        warn!("decimal(): failed to parse '{}', returning 0.0", s);
        0.0
    })
});
```

`"1,234.56"` and `"$200"` behave identically. Worth noting separately: `"inf"` and `"1e400"` *do* parse, to infinity — a different and equally wrong outcome.

**Fix.** Validate every `Decimal` at `CreateAlert` time and reject the request. Returning 0.0 from a price parse is never the safe default in either direction.

### F4 — The proto's own `NativeTrigger` example is uncompilable (HIGH · mechanical · grounded)
`proto/poligun/ninniku/alert/alert.proto:42`

`NativeTrigger.expression` is the primary user-authored surface of this feature, and its worked example is wrong twice. It uses message-construction syntax `TriggerResult{...}`, but the engine builds a plain `Context::default()` with no struct registered, and the `cel` crate's `structs` feature isn't even enabled — so that expression errors unconditionally. `parse_trigger_result` accepts only `Value::Map`. Separately, the example stores state as `string(new_hwm)` while `src/alert/mod.rs:13-14` documents that state is stored as floats for numeric comparison.

```
// proto/poligun/ninniku/alert/alert.proto:42-45
//   TriggerResult{
//     fired: price <= new_hwm - decimal('1.00'),
//     next_state: {'hwm': string(new_hwm)}
//   }
```
```rust
// src/alert/alert_engine.rs:263-272
let map = match value {
    Value::Map(ref m) => m,
    _ => return Err(format!("Expression must return a map with 'fired' key, got: {:?}", value)),
};
```

A user who copies the documented example gets a "successfully created" alert that errors on every tick, logged server-side and invisible to them.

**Fix.** Rewrite the example as the map form the translator itself emits: `{'fired': ..., 'next_state': {'hwm': new_hwm}}`, with a numeric watermark.

### F5 — The NaN sentinel raises an error in `cel` 0.14; it does not compare false (HIGH · scoped · confirmed)
`src/alert/alert_engine.rs:114`

The stub's safety argument is explicitly IEEE 754 semantics, but this evaluator doesn't use them. `cel` 0.14.0 compares doubles via `partial_cmp(...).ok_or(ExecutionError::NoSuchOverload)?`, so a NaN operand propagates an error out of the whole expression rather than yielding `false`.

```rust
// src/alert/alert_engine.rs:114-116
// NaN is the safe sentinel: all IEEE 754 comparisons against NaN return false,
// so no trigger fires regardless of direction or baseline type.
f64::NAN
```
```rust
// cel-0.14.0/src/common/types/double.rs:89-94
Ok(self.0.partial_cmp(&rhs.0).ok_or(ExecutionError::NoSuchOverload)?)
```

Combined with F9, an alert using a bar-based baseline doesn't quietly not-fire — it errors every tick and takes its sibling triggers down with it. The comment is load-bearing, so anyone maintaining this will reason from a false premise.

**Fix.** Correct the comment, and make the stub fail explicitly (or refuse the trigger at create time per F2) rather than relying on comparison semantics the evaluator doesn't have.

### F6 — `DeleteAlert` always fails, and `UpdateAlert` is unimplemented (HIGH · scoped · confirmed)
`src/server/mod.rs:664`

`create_alert` starts the bot immediately, so every alert reaches `BotStatus::Running`. `delete_alert` then calls `delete_bot` with no preceding stop, and `delete_bot` rejects running bots. Meanwhile `update_alert` returns `unimplemented` while the proto documents it as "Replace the AlertDefinition of an existing alert" with no disclaimer. The result is that no alert-scoped RPC can modify or remove an alert once created.

```rust
// src/bot/bot_manager.rs:191-193
if metadata.status == BotStatus::Running as i32 {
    return Err(format!("Cannot delete a running bot: {}", bot_id).into());
}
```
```
// proto/poligun/ninniku/ninniku.proto:60-61
// Each alert runs in its own AlertBot. CreateAlert creates (and starts) the
// AlertBot; DeleteAlert stops and removes it unconditionally.
```

There *is* an escape hatch — `UpdateBotStatus(alert_id, STOPPED)` then `DeleteAlert` works, because `alert_id == bot_id` — but it's undocumented, outside the alert contract, and requires knowing that equivalence. That's why this is HIGH rather than CRITICAL.

**Fix.** Have `delete_alert` stop the bot before deleting. Either implement `UpdateAlert` or mark it not-implemented in the proto.

### F7 — Per-trigger state is keyed by list position and survives a trigger-list change (HIGH · scoped · confirmed)
`src/bot/alert_bot.rs:63`

State is indexed by position in `AlertDefinition.triggers`, and the vector is only ever grown — never shrunk, cleared, or re-keyed. `BotEvent::ConfigUpdate` swaps the config inside `BotContext` **without recreating the `Box<dyn Bot>`**, so in-memory state survives an arbitrary trigger-list replacement. `UpdateAlert` being unimplemented doesn't close this: the generic `UpdateBotConfig` RPC accepts any `bot_id` and any `BotConfig` and reaches the same live `AlertBot`.

```rust
// src/bot/alert_bot.rs:62-65
let mut states = self.trigger_states.lock().await;
while states.len() < trigger_count {
    states.push(None);
}
```

Concretely: triggers `[0]=trailing_below BTCUSD` (hwm 95000), `[1]=rise_above AAPL`. Replace the list with a single `trailing_below AAPL price_offset 1.00`. `states[0]` still holds `{hwm: 95000}`, so `new_hwm = max(231.40, 95000) = 95000` and `fired = 231.40 <= 94999` → **true**, every cycle, forever.

**Fix.** Give `TriggerConfig` a stable identity and key state by it, or clear state on any config update. Either is fine; the positional scheme silently picks the worst of both.

### F8 — `time_unit` is a free string with a silent 60-second default (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:154`

Three new fields model time units as `string` ("e.g. `MINUTE`") while this repo already has `poligun.ninniku.marketdata.TimeUnit` and uses it on `Bars.time_unit` and `RenkoChart.time_unit` (convention ledger C3: 4 supporting references, 0 counterexamples before this branch). Nothing validates the string, and `lookback_duration` falls through to 60 seconds for anything it doesn't recognize while forwarding the raw string on to `reduce_bars`.

```rust
// src/alert/mod.rs:206-212
fn lookback_duration(lookback_bars: i32, multiplier: i32, time_unit: &str) -> String {
    let unit_seconds: i32 = match time_unit.to_uppercase().as_str() {
        "MINUTE" => 60,
        "HOUR" => 3600,
        _ => 60,
    };
    format!("{}s", lookback_bars * multiplier * unit_seconds)
}
```

`time_unit: "DAY"` with `lookback_bars: 20` asks for DAY bars over a 20-*minute* window — wrong by 1440×, silently. This is HIGH rather than MEDIUM because tightening `string` → `enum` on the same field number later is a wire-breaking change, so the shape costs a migration.

**Fix.** Use the existing `TimeUnit` enum. If the string must stay, reject unrecognized values instead of defaulting.

### F9 — One trigger's error discards every other trigger's result that cycle (MEDIUM · mechanical · confirmed)
`src/alert/alert_engine.rs:180`

`evaluate_alert_definition` propagates the first per-trigger error with `?`, throwing away the whole `results` vector — including triggers that already evaluated to `fired: true`. `AlertBot` then logs and returns without inspecting anything. The error sources are routine: `latest_quote`/`latest_trade` convert `Ok(None)` (no cached quote, illiquid or unsubscribed symbol) into an `ExecutionError`. The proto promises the opposite: "Each trigger maintains independent state across evaluations."

```rust
// src/alert/alert_engine.rs:179-180
let result =
    evaluate_trigger_config(trigger_config, state, last_eval_time, market_data.clone())?;
```

Verification trimmed this one: the finder claimed the already-advanced watermark makes the missed firing unrecoverable, but for `trailing_below`, `new_hwm = max(price, prev_hwm)` provably can't advance on a cycle where it fires. So a sustained breach re-fires next cycle — this is a delayed notification, not a lost one. Hence MEDIUM, not HIGH.

**Fix.** Collect per-trigger errors into the results vector instead of short-circuiting, and let the caller notify on the triggers that succeeded.

### F10 — Four declared fields have no reader (MEDIUM · scoped · confirmed)
`proto/poligun/ninniku/alert/alert.proto:238`

Each of these is accepted, stored, and ignored, with a doc comment that promises behavior:

- **`AlertDefinition.required_symbols`** (`alert.proto:238`) — "The engine subscribes to market data for these symbols once for the whole alert." Zero readers in `src/`. Nothing subscribes. This is the mechanism that would have been needed to make D1 work.
- **`EvalSchedule.market_hours_filter`** / **`MarketHoursFilter.regular_hours`** (`alert.proto:187`, `:193`) — zero readers. `pre_market`/`post_market` *are* disclosed as unimplemented, which affirmatively implies `regular_hours` is not. Setting it has exactly the same effect as omitting it, so an equity alert notifies at 3 a.m. on a stale quote.
- **`NativeTrigger.initial_state`** (`alert.proto:53`) — "Seed state for the very first evaluation." The only two references in the repo are the declaration and `initial_state: None` in the translator. The asymmetry is the sharp edge: the BuiltIn path *does* honor a seed via `TrailingBelow.water_mark`, so migrating the same alert to a `NativeTrigger` silently loses seeding.
- **`BotMetadata.can_trade`** (`bot.proto:20`) — written at `bot_manager.rs:147`, never read back. The uniqueness check deliberately re-derives it from `bot_config`, so the stored field is write-only and reads `false` for every bot created before this branch. `GetBotMetadata` returns it verbatim, so a UI would label an existing live trading bot as read-only.

```
// proto/poligun/ninniku/alert/alert.proto:233-238
// Symbols required across all triggers. The engine subscribes to market
// data for these symbols once for the whole alert.
repeated string required_symbols = 4;
```

**Fix.** For each: implement it, or delete it from the contract, or mark it not-implemented the way `pre_market` is. Shipping a field that does nothing is the one option that costs a breaking change later.

### F11 — Nothing validates or compiles a trigger until the first evaluation (MEDIUM · scoped · unverified)
`src/server/mod.rs:682`

`validate_alert_definition` can only check three presence conditions, because the code that could detect a malformed trigger — `translate_built_in_trigger` and `Program::compile` — runs exclusively on the evaluation path, on every tick, on a clone.

```rust
// src/server/mod.rs:685-700 (abridged)
if def.triggers.is_empty() { … }
if def.eval_schedule.as_ref().and_then(|s| s.interval.as_ref()).is_none() { … }
if def.sink.is_none() { … }
```

This is the root cause behind F3, F4, and part of F2: `CreateAlert` returns 200 with an `alert_id` for an alert that will error every interval. With `UpdateAlert` unimplemented and no Get/List-alert RPC, the user's only remedy is delete-and-recreate — which F6 says doesn't work either.

**Fix.** Call `translate_built_in_trigger` and `Program::compile` at create time and surface failures as `invalid_argument`. Translating once at create rather than every tick is also strictly cheaper.

### F12 — Alerts re-notify every cycle while the condition holds (MEDIUM · scoped · confirmed)
`src/bot/alert_bot.rs:89`

The notify loop acts on `result.fired` with no comparison against the previous cycle. `RiseAbove`/`FallBelow` emit no `next_state` at all, so no state exists that could encode "already fired", and there is no cooldown, dedup, or rate limit anywhere in `src/` or `proto/` (checked against a wide synonym list).

```rust
// src/bot/alert_bot.rs:89-93
for (i, result) in results.iter().enumerate() {
    …
    if !result.fired { continue; }
```

`rise_above AAPL 200` at a 30 s interval, with AAPL sitting at 231, dispatches ~780 times per trading day for one crossing. Today that's log volume, because delivery is a stub; it becomes user-visible spam the moment F1 is fixed. It's MEDIUM rather than HIGH because the fix doesn't need a schema change — `next_state` is already a generic `Struct`, so an edge marker is an internal change to the translator.

**Fix.** Emit a `fired` marker in `next_state` for the built-in triggers and notify only on the false→true transition, or add an explicit cooldown to `EvalSchedule`.

### F13 — `UpdateBotConfig` bypasses the new per-account trading-bot cap (MEDIUM · scoped · confirmed)
`src/bot/bot_manager.rs:166`

Relaxing the rule from "one bot per account" to "one *trading* bot per account" moved the uniqueness check behind `if new_can_trade`, but only in `create_bot`. `update_bot_config` replaces the config wholesale and re-checks nothing.

```rust
// src/bot/bot_manager.rs:166
let new_metadata = BotMetadata { bot_config: Some(bot_config.clone()), ..metadata };
```

Path: account A has trading bot B1. `CreateAlert` for A succeeds (AlertBot, check skipped) → B2. `UpdateBotConfig(B2, NoopBotParams)` succeeds, so B2 is now a non-alert bot on A with `can_trade` still stale `false`. **This is newly reachable** — the pre-branch check was unconditional, so a second bot on an account was categorically impossible. Severity is MEDIUM rather than HIGH only because neither existing bot variant actually submits orders today (no `submit_order`/`place_order` exists anywhere), so the cap protects an invariant that isn't yet load-bearing.

**Fix.** Re-derive `can_trade` and re-run the uniqueness check in `update_bot_config`.

### F14 — `AccountInfo` PDT field removal rides along in an alerts branch (MEDIUM · needs-decision · unverified)
`proto/poligun/ninniku/alpaca/account_info.proto:31`

`pattern_day_trader` (7) and `daytrade_count` (21) are removed and reserved, and the Rust struct fields that populated them deleted, in a branch whose stated purpose is price alerts. The `reserved` markers are the correct ritual and aren't the problem — the problem is that a wire-visible removal of two PDT-compliance signals from a trading service is bundled into an unrelated feature branch, which is exactly how breaking changes reach production unreviewed.

```
// proto/poligun/ninniku/alpaca/account_info.proto:31
reserved 7; // Was pattern_day_trader
```

In-repo blast radius appears to be a stale generated frontend client only; I can't see consumers outside this repo.

**Open question.** Was this intended as part of this branch, and does any consumer outside this repo read `AccountInfo` fields 7 or 21? If it's intentional but unrelated, it belongs in its own change.

### F15 — Uncommitted debug log reports every trigger as fired (LOW · mechanical · confirmed)
`src/bot/alert_bot.rs:90` · **not yet committed**

The one uncommitted source change adds an `info!` *above* the `!result.fired` guard, so it logs "trigger 0 fired — false" for every non-firing trigger on every cycle, using the same wording as the real firing message at line 106.

```rust
// src/bot/alert_bot.rs:90-93
info!("AlertBot: trigger {} fired — {}", i, result.fired);
if !result.fired {
    continue;
}
```

An operator grepping logs for `fired` can't distinguish a real alert from a no-op.

**Fix.** Delete it, or move it below the guard and reword it.

---

## Design notes

These are opinions, labelled as such — either `TASTE` verdicts, refuted-but-interesting findings, or convention rules the ledger scored `mixed`.

- **Breakout window bounds.** The generated CEL window is `[now - lookback, now]` while the proto says "last N **completed** bars". This *looks* like an off-by-one that would defeat `price > bar_high`, but verification refuted it: bars enter the table only via Alpaca's closed-bar feeds, so no row exists for the in-progress interval. What survives is minor — `context.last_eval_time` defaults to `now` on the first cycle after each process start (`alert_engine.rs:210-212`), giving the `High`/`Low`/`Bar` baselines a zero-width window exactly once. Currently masked by the `reduce_bars` stub.
- **`Bar::get_highest_high` is dead code** (`src/postgres/bar.rs:200`) — zero callers. Presumably the intended `reduce_bars` backend. Its `start_time >= $6 AND start_time <= $7` bounds are inclusive at both ends, which is worth a second look when it's wired up.
- **`type TranslationError = String` / `type EngineError = String`.** The repo uses `Box<dyn Error + Send + Sync>` in 34 files but `Result<_, String>` on public fns in 4 (`create_order.rs:135`, `server/proto.rs:101`, `fetch_history.rs:129/151/181`, `ta/renko.rs:140`). Ledger verdict: **mixed** — the repo is inconsistent here, so this isn't a finding against the author. Flagging it as a team question rather than a defect.
- **`pub mod alert_bot;` exposes a module whose only item is `pub(super)`** — the `pub` is inert. `src/bot/` is 5 private `mod` vs 3 `pub mod`, ledger verdict **mixed**, so no finding; noting it because the visibility looks unintentional.
- **`src/alert/mod.rs` holds 220 lines of translation logic.** Four `mod.rs` files in this repo are thin facades and six carry substantial implementation — ledger verdict **mixed**. Personal preference would be `src/alert/translate.rs` with `mod.rs` as the facade, but the repo genuinely doesn't have a rule here.
- **`percent_offset` units are undocumented.** `TrailingAbove/TrailingBelow.percent_offset` generates `new_lwm * (decimal('1') + decimal('{}'))`, implying a fraction — but the proto never says. A user entering `5` for "5%" gets a 6× threshold. Worth one sentence in the proto.
- **`build.rs` dropping serde derives from `.poligun.ninniku.bot`** — checked, no consumer cost. `BotMetadata` is persisted as base64 prost bytes, not JSON, and nothing else serializes bot types. The change was likely forced by the new `google.protobuf.Struct` dependency.

---

## Could not resolve

- **Whether equity rows could already exist in the shared Postgres tables from an out-of-band writer** (a DBA backfill, a decommissioned job, another service). Nothing in this repo writes them, which is what D1 rests on, but the database is shared state. Settling it would take a `SELECT DISTINCT symbol FROM quotes` against the real database, or confirmation that no other service writes it.
- **Whether any consumer outside this repo reads `AccountInfo` fields 7 or 21** (F14). Only the repo owner can answer.

---

## Proposed memory (not written)

No knowledge base exists for this repo — neither `<repo>/.claude/knowledge/` nor `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/` — and this run was non-interactive, so nothing was created. If you want this kept for future reviews, say where and I'll write it. The entries worth keeping:

1. **Alerts *are* bots.** `CreateAlert` → `create_bot` + `start_bot`; `alert_id == bot_id`. Status transitions go through an async ack channel, so Redis status lags the task by one hop. Any alert-lifecycle question has to check both the alert RPC *and* the generic bot RPC that reaches the same object — F6 and F13 are invisible if you read only `src/server/mod.rs`.
2. **`BotEvent::ConfigUpdate` mutates the config in place and does *not* recreate the `Box<dyn Bot>`.** In-memory bot state therefore survives an arbitrary config change, including a change of `bot_params` variant. This is what makes F7 reachable.
3. **The market-data plane is crypto-only.** Three tables, one `batch_upsert` each, six call sites, all pinned to `/v1beta3/crypto/us`. No live-API fallback on cache miss. Re-check before believing any feature works for equities.
4. **Cheap high-yield first move on this repo:** grep declared proto fields for readers. On this branch that single check found four dead fields (F10) and was the highest-yield angle by a wide margin.
5. **Not a vulnerability:** user values are interpolated into CEL source text via `format!`, but `NativeTrigger.expression` already accepts arbitrary user CEL by design, so escaping grants no capability the caller lacks. The real consequence is that a malformed value yields a program accepted at create and permanently uncompilable at eval (F11).
