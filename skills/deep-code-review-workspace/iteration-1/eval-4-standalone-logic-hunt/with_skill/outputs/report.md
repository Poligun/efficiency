## Review: alert subsystem — CEL-evaluated price triggers on a scheduled bot (`cel-alert` vs `e85ca8d9`)

Your instinct is right, and I think I can name what's bothering you: **the whole subsystem is built to fail silently.** Almost every failure path in this branch converts an error into a value — a `0.0`, a `NaN`, a `false`, an `Ok(interval)` — and returns success. For an alerting product that inverts the two things that matter: an alert that quietly never fires looks exactly like a market that never moved, and an alert that fires on a garbage threshold looks exactly like a real crossing. Three of those paths are individually shipping-blocking. Separately, `DeleteAlert` cannot succeed for any alert `CreateAlert` produced — `create_alert` always starts the bot, and `delete_bot` refuses to delete a running bot.

**Angles run.** All ten. The six core angles (lifecycle, repeat-fire, boundary/window, fallback/sentinel, partial-failure, declared-surface) plus all four conditional angles, whose gates all fired: A7 taint (`format!` builds CEL source that `Program::compile` executes), A8 numeric (unvalidated `i32` arithmetic and `BigDecimal → f64` on money), A9 identity (per-trigger state keyed by list position), A10 concurrency (two mutexes, `block_in_place`, broadcast/mpsc, an ignored `CancellationToken`). Nothing was gated out. The diff is ~1150 lines excluding the `Cargo.lock` churn, so nine angles ran as parallel subagents and A9 ran in-context.

Two scope notes. **There is no knowledge base for this repo yet**, so nothing was recalled and every claim below is quoted from the current working tree this session — including your uncommitted edit to `alert_bot.rs`. And **there are no tests anywhere under `src/alert/` or `src/bot/`** (`rg '#\[test\]|#\[tokio::test\]'` → zero hits); findings 1, 3 and 9 would each have died to a single unit test on `evaluate_native_trigger`.

---

## The behavior model I reviewed against

```
ENTITIES
  Alert ≡ Bot (alert_id IS bot_id). STOPPED --start_bot--> RUNNING (via async ack) --> deleted.
    No StopAlert, no ListAlerts; UpdateAlert is unimplemented.
  Trigger — BuiltIn translated to Native at *eval* time, not at create time.
    Per-trigger CEL state: None -> Struct, carried across ticks, keyed by LIST POSITION, in-memory only.
  AlertBot instance — (trigger_states, last_eval_time). Built once in resume_bot;
    never rebuilt on a config change.
  Evaluation task — one per resume_bot; ignores its CancellationToken; exits only on a broadcast Stop.

EFFECTS
  Notify a Telegram sink when a trigger fires   (today: two log lines and a TODO)
  Compile + execute caller-influenced CEL source, every trigger, every tick
  Blocking market-data reads against a Postgres-backed quote/trade cache
  Redis writes of BotMetadata; spawn/stop of background tasks

PROMISES  (the proto is the only written contract)
  "fires ... when ANY trigger returns fired:true. Each trigger maintains INDEPENDENT state"
  "If omitted by the expression, the previous state is carried forward unchanged"
  "Seed state for the very first evaluation"                        (initial_state)
  "The engine subscribes to market data for these symbols"          (required_symbols)
  "Binding names from the trigger are substituted as {{name}}"      (message_template)
  "DeleteAlert stops and removes it unconditionally"
  "highest high of the last lookback_bars COMPLETED bars"           (breakout)
  "Decimal ... without losing precision" / "API will not perform any validation"

TRIGGERS
  CreateAlert -> create_bot + start_bot (RUNNING within milliseconds)
  evaluate() every eval_schedule.interval (default 30s; 5s on any error)
  UpdateBotConfig broadcast -> live definition swap on a running AlertBot
  Process restart -> resume_bots revives every RUNNING bot with fresh, empty in-memory state
```

Everything below traces to a line in that model. Ordered severity descending, then fix clarity ascending.

---

### CRITICAL — A failed price parse becomes `0.0`, inverting the comparison it feeds
`src/alert/alert_engine.rs:31-36` · fix: scoped · angle A4 (corroborated by A6, A7, A8)

`Decimal.value` is a raw string, `well_known_types.proto` states outright that the API performs no format validation, and `validate_alert_definition` never inspects a `Decimal`. When the string doesn't parse, the CEL `decimal()` function substitutes zero and logs a warning.

```rust
ctx.add_function("decimal", |s: Arc<String>| -> f64 {
    s.parse::<f64>().unwrap_or_else(|_| {
        warn!("decimal(): failed to parse '{}', returning 0.0", s);
        0.0
    })
});
```

This is the exact inverse pair, in one file, twelve lines apart:

```rust
let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);   // mod.rs:32  RiseAbove
let expr = format!("{{'fired': price <= decimal('{}')}}", price.value);   // mod.rs:41  FallBelow
```

**Trace.** A client sends `RiseAbove { price: Decimal { value: "1,250.00" } }` — comma-grouped, a completely ordinary client-side format, and `""` is what you get from a default-constructed `Decimal`. `"1,250.00".parse::<f64>()` fails, the threshold becomes `0.0`, the expression becomes `price >= 0.0`, and the alert fires on the first tick and every tick after — 120 notifications an hour at the default 30 s interval. The same input on `FallBelow` yields `price <= 0.0`, which is false for every positive price: the alert is silently dead for its entire life. Both trailing variants fail toward always-fire — `new_hwm - decimal('bad')` is `new_hwm - 0.0`, and `price <= max(price, prev_hwm)` is a tautology. Note also that `parse::<f64>` *succeeds* on `"inf"` and `"NaN"`, so `decimal('nan')` makes every comparison false, forever, with no warning at all.

**Fix.** Parse `Decimal.value` into a `BigDecimal` in `validate_alert_definition` and reject non-finite or unparseable values at the RPC boundary, then interpolate the *parsed* value. Make `decimal()` return `ExecutionError` rather than a number — the sibling functions at `:63-67` already do exactly that for missing data.

---

### CRITICAL — `DeleteAlert` can never succeed for an alert that `CreateAlert` created
`src/bot/bot_manager.rs:191-193` · fix: scoped · angle A1 (corroborated by A5, A6)

Each function is fine on its own; the composition is a guaranteed failure.

```rust
// bot_manager.rs:191 — delete_bot, the only thing delete_alert calls
if metadata.status == BotStatus::Running as i32 {
    return Err(format!("Cannot delete a running bot: {}", bot_id).into());
}
```

**Trace.** `create_alert` (`server/mod.rs:618-627`) calls `create_bot` — which persists `status: BotStatus::Stopped` (`bot_manager.rs:143`) — and then immediately `start_bot`, which spawns `bot_evaluation_loop`. The loop's first statement sends `BotAckEvent::Started` (`bot_loop.rs:15`), and `bot_manager_loop` flips the stored status to `Running` (`bot_manager.rs:352-357`). So every successfully created alert is `RUNNING` within milliseconds, and `delete_alert` — which never calls `stop_bot` — hits the guard above and returns `Internal: Cannot delete a running bot: <id>`. `ninniku.proto:60-61` promises the opposite in so many words: *"DeleteAlert stops and removes it unconditionally."* There is no `StopAlert`; the only escape is to know that you must first call the unrelated `UpdateBotStatus` RPC.

The narrow window where delete *does* succeed is worse than the failure. If the request lands before the `Started` ack is processed, the guard passes, the metadata is deleted — and `delete_bot` never sends `BotEvent::Stop`, while `bot_evaluation_loop` ignores its `CancellationToken` (`bot_manager.rs:251`, `|_ct| async move`). The task now has no metadata, so shutdown's stop-broadcast (which enumerates metadata) never names it. It evaluates forever until the process dies.

**Fix.** `delete_alert` should stop then delete, and wait for the `Stopped` ack — `stop_bot` is async-acked, so this isn't a one-liner. Making `bot_evaluation_loop` honor its `CancellationToken` closes the orphan half.

---

### CRITICAL — One trigger's error aborts every other trigger, discarding fires that already happened while keeping their state
`src/alert/alert_engine.rs:177-189` · fix: scoped · angle A5 (corroborated by A2, A3, A4, A7)

```rust
for (i, trigger_config) in definition.triggers.iter().enumerate() {
    let state = states[i].as_ref();
    let result =
        evaluate_trigger_config(trigger_config, state, last_eval_time, market_data.clone())?;  // :180

    if let Some(ref next) = result.next_state {
        states[i] = Some(next.clone());                                                         // :183
    }
    results.push(result);
}
```

`alert.proto:223-225` is explicit that this is not a transaction: *"The alert fires ... when **any** trigger returns `TriggerResult{fired: true}`. Each trigger maintains **independent** state across evaluations."* Any-fires semantics means independent items, and abort-on-first-error is the wrong shape. Three losses stack on one failure: triggers `i+1..N` are never evaluated; the `results` vector holding `fired: true` for triggers `0..i` is thrown away by the `?`; and `states[0..i]` were already mutated in place on the caller's `&mut Vec` at `:183`, so those writes survive the `Err`.

**Trace.** Triggers `[0] = TrailingBelow(AAPL, price_offset 5.00)`, `[1] = RiseAbove(TSLA, 300)`, TSLA not in the quote cache.
- t=0: AAPL at 100 → `states[0] = {hwm: 100.0}`. TSLA errors, cycle returns `Err`.
- t=30s: AAPL drops to **94** → `new_hwm = max(94,100) = 100`, `fired: 94 <= 95` → **true**, and `states[0] = {hwm: 100}` is committed at `:183`. Then trigger 1 errors, `?` fires, and the `fired: true` is dropped. `alert_bot.rs:79-85` logs and returns `Ok(interval)`.
- t=60s: AAPL recovers to 97 → `97 <= 95` is false. **Not fired.**

The stop-loss crossing isn't delayed, it's permanently lost: the state that would have re-detected the edge was advanced past it before the abort. And this is the *normal* path, not an exceptional one — `latest_quote` turns a cache miss into a hard error (`:63-66`), and `required_symbols` is never read (finding 8), so nothing subscribes the symbol in the first place.

**Fix.** Collect a `Result` per trigger, `continue` on error, return the successful results plus a per-trigger error list. Commit `states[i]` only alongside a delivered notification.

---

### HIGH — `last_eval_time` advances even when the evaluation failed, so that window is never examined again
`src/bot/alert_bot.rs:76-85` · fix: mechanical · angle A3 (corroborated by A4, A5, A10)

```rust
// Update last_eval_time regardless of evaluation outcome
*self.last_eval_time.lock().await = Some(Utc::now());

let results = match results {
    Ok(r) => r,
    Err(e) => {
        error!("AlertBot: evaluation error: {}", e);
        return Ok(interval);
    }
};
```

The comment says this is deliberate, which is why it's worth naming: `last_eval_time` is the low end of a window. `Baseline::High`, `Low` and `Bar` all translate to `reduce_bars(..., context.last_eval_time, context.now, ...)` (`mod.rs:171-185`). Advancing `a` past a window whose work failed means that window's bars are below every future `a`, forever.

**Trace.** 30 s interval, `Baseline::High` on 1-minute bars. 10:00:00 eval succeeds, `a := 10:00:00.2`. 10:00:30 eval errors, but `a := 10:00:30.3` anyway. 10:01:00 eval succeeds with window `[10:00:30.3, 10:01:00.1]`. The bar starting 10:00:00 was only ever a candidate for the failed window. It is now permanently unreachable — and with `Baseline::High`, that bar is precisely the session spike the alert existed to catch.

Two smaller boundary problems ride along on the same lines. `now` is sampled *inside* `evaluate_native_trigger` (`alert_engine.rs:23`), i.e. once **per trigger**, while the next `a` is a fourth, strictly later sample taken here after evaluation — so the interval between a trigger's own `now` and this write is covered by no window at all (≈255 ms with three triggers at 85 ms per market-data round trip). And on the very first evaluation `last_eval_time` is `None`, which `build_context_map:210-212` substitutes with `now`, producing a zero-width `[t, t]` window — which recurs on every process restart, because this field is in-memory only.

**Fix.** Sample `now` once in `evaluate_alert_definition`, thread it down, and advance `last_eval_time` to *that* value only for triggers that succeeded.

---

### HIGH — The bot's control channel is unreliable in three independent ways
`src/bot/bot_loop.rs:33-73` · fix: scoped · angle A10 (corroborated by A1)

The evaluation loop reads `Stop` and `ConfigUpdate` only inside one `tokio::select!`, and three separate things route around it.

```rust
let wait_duration = match result {
    Err(e) => { error!(...); tokio::time::sleep(Duration::from_secs(5)).await; continue; }
    Ok(duration) if duration <= chrono::Duration::zero() => { error!(...); sleep(5s).await; continue; }
    Ok(duration) => duration,
};

tokio::select! {
    Ok(event) = bot_event_receiver.recv() => { ... }
    _ = tokio::time::sleep(wait_duration.to_std()?) => {}
}
```

**(a) `continue` skips the `select!` entirely.** A bot that returns `Err` or a non-positive duration never reaches the only place it reads its events — permanently. **Trace:** `CreateAlert` with `eval_schedule.interval { seconds: 0 }` passes validation (presence is checked, magnitude is not), so `AlertBot::evaluate` returns `Duration::zero()` and the loop takes the second `continue` forever. That alert is now unstoppable (`stop_bot` returns `Ok` to the caller but the bot never acks, so status stays `RUNNING`), undeletable (finding 2), unupdatable, hammers market data every 5 s, and at shutdown `bot_manager_loop` blocks in `while !stopping_bot_ids.is_empty()` waiting for an ack that can never arrive. The same trap is reachable by pointing `UpdateBotConfig` at an alert with `noop_bot_params` — `alert_bot.rs:35-40` then returns `Err` every tick.

**(b) Broadcast lag silently drops `Stop`.** `broadcast::channel::<BotEvent>(10)` and `Ok(event) = recv()` — when `recv()` returns `Err(RecvError::Lagged(n))` the pattern fails to match, the branch is disabled for that `select!` with no log, and the `n` dropped events are gone. The shutdown fan-out at `bot_manager.rs:386-391` sends one `Stop` per bot in an await-free `for` loop; with more running bots than the ring holds, the earliest `Stop` is evicted before any receiver polls, and that bot never stops. A bot parked in `block_in_place` on a Postgres query cannot poll at all during that window.

**(c) Every event wakes every bot and cancels its remaining interval.** The `select!` completes on *any* `BotEvent`; a non-matching `target_bot_id` falls through the match arm, the `select!` returns, and the outer loop immediately re-evaluates — discarding the rest of `wait_duration`. One `UpdateBotConfig` RPC forces an unscheduled evaluation on every other bot in the process, each a fresh burst of blocking queries against the same 10-connection pool.

**Fix.** Validate `interval > 0` at the boundary; replace `continue` with a `sleep_until(deadline)` inside the `select!`; match `Err(RecvError::Lagged)` explicitly; add a `_ = ct.cancelled() => break` arm so the already-available `CancellationToken` becomes the reliable stop path.

---

### HIGH — Per-trigger state is keyed by list position and survives a live definition swap
`src/bot/alert_bot.rs:60-65` · fix: scoped · angle A9 (corroborated by A1, A2, A4, A5)

```rust
// Synchronise the states vector length with the current trigger count
let trigger_count = definition.triggers.len();
let mut states = self.trigger_states.lock().await;
while states.len() < trigger_count {
    states.push(None);
}
```

Grow-only, position-keyed, and nothing ties an entry to the trigger that produced it. `UpdateAlert` is unimplemented, so it's tempting to call this latent — it isn't. `UpdateBotConfig` is fully implemented, `validate_bot_config` accepts any `bot_params` including `AlertBotParams`, and the resulting `BotEvent::ConfigUpdate` reaches the running bot at `bot_loop.rs:55-58`, which calls `context.update_bot_config(...)` — swapping the definition *behind* the live `AlertBot`. I checked: `create_bot_from_config` has exactly one caller, `bot_manager.rs:241` in `resume_bot`, so the `AlertBot` object and its `trigger_states` are never rebuilt.

**Trace.** Trigger 0 is `TrailingBelow(AAPL, price_offset 1.00)` and has accumulated `{'hwm': 250.0}` over the session. An `UpdateBotConfig` replaces trigger 0 with `TrailingBelow(NVDA, price_offset 1.00)`. Nothing shrinks or clears, so NVDA reads `states[0]`, and `'hwm' in context.state` (`mod.rs:68`) is true. NVDA at 120: `new_hwm = max(120, 250) = 250`, `fired: 120 <= 249` → **true immediately**, and because `max_decimal` is monotone the water mark never decays back down — it fires every cycle from then on, on a 130-point drawdown that never happened. Removing a trigger shifts every later trigger's state by one; a removed trigger's entry stays resident forever and is adopted by whatever later occupies the index.

**Fix.** Key state by trigger identity rather than position, or clear `trigger_states` on any definition change. `TriggerConfig` has no id field today, so the cheap version is to clear.

---

### HIGH — Trigger state and `last_eval_time` are in-memory only; a restart silently re-anchors every trailing stop
`src/bot/alert_bot.rs:11-24` · fix: scoped · angle A2 (corroborated by A1, A3, A8)

```rust
pub(super) struct AlertBot {
    /// Per-trigger CEL state, indexed by trigger position in `AlertDefinition.triggers`.
    trigger_states: Mutex<Vec<Option<prost_types::Struct>>>,
    /// Wall-clock time of the previous evaluation cycle, for `context.last_eval_time`.
    last_eval_time: Mutex<Option<DateTime<Utc>>>,
}
```

`rg trigger_states src/` matches only these lines and `alert_bot.rs:62`. What *is* persisted is `BotMetadata` — the whole `AlertDefinition` — via prost+base64 into Redis (`bot_metadata.rs:74-79`); `AlertBotParams` has no field for state. And restart is a routine path: shutdown deliberately leaves `status = Running` in Redis so `resume_bots` (called from `main.rs`) revives the bot, which goes through `create_bot_from_config` → `AlertBot::new(trigger_count)` → `vec![None; n]`.

**Trace.** `TrailingBelow(AAPL, price_offset 1.00)`, no `water_mark` seed. The session builds `hwm = 150.00`; the live stop sits at 149.00. You deploy while AAPL is at 148.50 — the alert *should* fire on the next tick. Post-restart `states[0]` is `None`, so the binding takes its fallback branch (`initial_wm` is the literal string `"price"` when `water_mark` is absent, `mod.rs:62`): `prev_hwm = 148.50`, threshold 147.50, `148.50 <= 147.50` → **false**. The trailing stop silently re-anchored $1.50 lower and the alert that was one tick from firing never fires. Nothing logs that this happened.

**Fix.** Persist `trigger_states` alongside the definition, or state in the proto that state is best-effort and resets on restart. Note the second option interacts with finding 9 — `initial_state` is the field that would let a caller re-seed, and it has no reader.

---

### HIGH — Four contract fields have no reader at all, and one of them breaks the feature end to end
`proto/poligun/ninniku/alert/alert.proto` · fix: scoped · angle A6

Each grep below was run with `--glob '!target'` so generated code isn't counted as a consumer.

| Field | Declared | `rg` result | What a caller who sets it gets |
|---|---|---|---|
| `AlertDefinition.required_symbols` | `:233-238` — *"The engine subscribes to market data for these symbols once for the whole alert"* | **1 hit: the proto line itself.** Zero in `src/` | Nothing subscribes. `latest_quote` resolves to `Quote::get_latest_quote`, a plain `SELECT ... ORDER BY time DESC LIMIT 1` fed only by the separate `Subscribe` RPC's websocket pipeline. The alert then errors on **every** evaluation with `no data for symbol: X` — which, per finding 3, also kills every sibling trigger. |
| `EvalSchedule.market_hours_filter` / `MarketHoursFilter.regular_hours` | `:186-193` | 1 hit each, both the proto | Silently ignored; `alert_bot.rs:50-58` reads `interval` only. The alert evaluates overnight, weekends and holidays against stale cached quotes and notifies when the caller explicitly asked it not to. (`pre_market`/`post_market` say *"Not yet implemented"* — that's disclosure, not a defect. `regular_hours` carries no such note.) |
| `NativeTrigger.initial_state` | `:51-53` — *"Seed state for the very first evaluation"* | 2 hits: the proto, and `mod.rs:160` writing `initial_state: None` | The first evaluation sees `context.state == {}` instead of the seed, so an expression written per the doc as `context.state['hwm']` raises no-such-key. The built-in path works, but through a different mechanism (a ternary baked into the binding), which is exactly why this gap survives testing via `BuiltInTrigger`. |
| `Sink.TelegramNotification.message_template` | `:210-213` — *"Binding names ... substituted as `{{name}}`"* | No substitution code exists anywhere in `src/` | The user receives the literal string `AAPL ask {{price}} crossed above {{threshold}}`. Bindings are consumed into the CEL `Context` at `alert_engine.rs:131` and dropped when the function returns — they aren't even *available* to a future substitution pass. `validate_alert_definition` *requires* `sink` to be present, so the server mandates a field whose entire documented effect is unimplemented. |

**Fix.** Wire `required_symbols` into a subscription on create (this one is load-bearing, not cosmetic), read `initial_state` when `states[i]` is `None`, implement or remove `{{name}}`, and either implement `regular_hours` or mark it not-yet-implemented like its two siblings.

---

### HIGH — The CEL result protocol is undocumented, unexecutable as documented, and silently tolerant of the wrong shape
`proto/poligun/ninniku/alert/alert.proto:40-46` vs `src/alert/alert_engine.rs:263-278` · fix: scoped · angle A6/A4 · *contract mismatch*

The proto documents the trigger expression with a worked example:

```
//   TriggerResult{
//     fired: price <= new_hwm - decimal('1.00'),
//     next_state: {'hwm': string(new_hwm)}
//   }
```

That expression cannot execute. `Cargo.toml:11` declares `cel = "0.14.0"` with default features, and I checked the vendored crate: `default = ["regex", "chrono"]`, while `structs = []` is a separate opt-in feature. Without it, `cel-0.14.0/src/objects.rs:1511-1518` handles a struct literal as

```rust
Expr::Struct(strct) => {
    #[cfg(not(feature = "structs"))]
    { Err(ExecutionError::InternalError(format!("Found struct {name}, feature not enabled!"))) }
```

So a caller who copies the contract's own example gets a hard evaluation error on every tick, surfaced only as one `error!` line, forever. Even with the feature enabled it would still fail, because `parse_trigger_result` requires a bare `Value::Map`. The real protocol is `{'fired': ..., 'next_state': ...}` — correctly stated in a Rust doc comment at `mod.rs:13`, and nowhere in the contract the caller reads. The example also writes `string(new_hwm)` while `mod.rs:14` says state is stored as floats, so the two documents disagree with each other as well.

The shape check is then too permissive in the other direction. A non-map result is a real error (`:266-271`), which makes this look validated — but the `fired` key itself is not:

```rust
let fired = map.map
    .get(&Key::String(Arc::new("fired".to_string())))
    .and_then(|v| if let Value::Bool(b) = v { Some(*b) } else { None })
    .unwrap_or(false);
```

**Trace.** `NativeTrigger { expression: "{'fired': 1}" }` — truthy in most template languages. `Value::Int(1)` isn't `Value::Bool`, so it becomes `None`, then `false`. A typo like `{'firing': ...}` does the same. The alert passes `CreateAlert`, reports `Running`, evaluates cleanly, and never fires — indistinguishable from a genuine non-crossing. `next_state` has the same hole: `cel_map_to_prost_struct` returns `None` for any non-map, which collapses "user omitted it" and "user's expression produced the wrong type" into the same silent outcome, freezing the water mark forever.

**Fix.** Enable the `structs` feature or correct the proto example to the bare-map form (and reconcile `string(new_hwm)` with the float claim); return an error when `fired` is present but not a bool, or absent entirely; compile the expression during `validate_alert_definition` so a bad trigger is rejected synchronously instead of becoming a background log line.

---

### MEDIUM — Numeric domains are unchecked: an i32 overflow, a 1440× unit fallthrough, and two panics
`src/alert/mod.rs:206-213`, `src/bot/alert_bot.rs:53-58` · fix: mechanical · angle A8

```rust
fn lookback_duration(lookback_bars: i32, multiplier: i32, time_unit: &str) -> String {
    let unit_seconds: i32 = match time_unit.to_uppercase().as_str() {
        "MINUTE" => 60,
        "HOUR" => 3600,
        _ => 60,
    };
    format!("{}s", lookback_bars * multiplier * unit_seconds)
}
```

- **Unit fallthrough.** `time_unit` is a free-form string with no allowlist. `BreakoutAbove { lookback_bars: 20, multiplier: 1, time_unit: "DAY" }` — the canonical use of the trigger — emits `duration('1200s')`. A 20-**day** breakout becomes a 20-**minute** breakout: wrong by 1440×, silently. `"WEEK"` is 10,080× and `""` (the proto3 default when the field is omitted) silently means MINUTE. The raw string is *also* passed through to `reduce_bars` verbatim, so the window and the bar size disagree with each other. `"HOUR"` is accepted here but `postgres::models::TimeUnit` has only `Minute`, so it has no bar rows to match either.
- **i32 overflow.** Both ints come straight off the wire, unvalidated, and the product is unchecked `i32`. The smallest overflow is `lookback_bars * multiplier > 35_791_394`. Release builds wrap: `40_000 × 1_000 × 60` = 2.4e9 → `-1_894_967_296` → `duration('-1894967296s')`, which cel's parser accepts, giving a window whose *start* is 60 years after its *end*. Debug builds panic inside `evaluate`, killing the task with nothing to restart it — and `Cargo.toml:48-49` sets `[workspace.lints.clippy] panic = "deny"`.
- **`chrono::Duration::seconds` panics.** `interval { seconds: i64::MAX }` passes validation (presence only) and panics at `alert_bot.rs:56`; `{ seconds: 9_223_372_036_854_775, nanos: 999_999_999 }` panics on the `+` instead. The safe pattern already exists in-tree — `NoopBot` clamps with `max(1, ...)`.
- **Non-positive offsets.** Nothing requires `price_offset > 0`. `TrailingBelow` with `price_offset "0"` gives `price <= max(price, prev_hwm)` — true on the first tick and every tick after. A negative offset makes it unconditional.

**Fix.** Compute in `i64` with `checked_mul`; parse `time_unit` into the `TimeUnit` enum and reject unknown units; use `try_seconds`; bound `lookback_bars`, `multiplier` and the offsets to a positive range in `validate_alert_definition`.

---

### MEDIUM — `validate_alert_definition` checks presence only, is bypassable, and user strings reach CEL source unescaped
`src/server/mod.rs:682-701` · fix: scoped · angle A7

The validator checks exactly three things: `triggers` non-empty, `eval_schedule.interval` **present**, `sink` present. It never descends into a `TriggerConfig`, so every numeric and string field inside a trigger arrives unchecked — which is the shared root of findings 1 and 10.

It is also bypassable. `CreateBot` (`server/mod.rs:547-565`) and `UpdateBotConfig` (`:567-586`) both accept an arbitrary `BotConfig` through `validate_bot_config`, which only checks `bot_params.is_some()`. An `AlertBotParams` submitted that way reaches a live `AlertBot` having passed no alert validation at all — with `triggers: []`, or `interval: None`, or anything else.

And the strings are interpolated into CEL source text that `Program::compile` then executes:

```rust
Some(BaselineType::Ask(())) => format!("latest_quote('{}').ask", symbol),   // mod.rs:168
```

**Escalation question, answered explicitly:** this is **not** a privilege escalation. `TriggerConfig` is a oneof, and the same caller on the same RPC may send `NativeTrigger.expression` — arbitrary CEL, by design. Anything reachable by injecting through `BuiltInTrigger` is reachable legitimately through `NativeTrigger`, and the sandbox exposes only `Env::stdlib()` plus the six registered functions — no filesystem, process, or network primitives. So I'm reporting it as a robustness defect, not a security finding.

It still matters as a robustness defect, in two directions. A payload like `symbol = "AAPL').bid + latest_quote('TSLA"` yields `latest_quote('AAPL').bid + latest_quote('TSLA').ask` — a single field read silently becomes cross-symbol arithmetic, and `symbol` is interpolated at *two* sites for breakout triggers. More mundanely, a symbol or decimal containing one apostrophe (`IT'S`, `1.00'`) produces `Program::compile` failure — which, per finding 3, kills the entire alert on every tick, forever, with no feedback to the caller who created it.

**Fix.** One change covers all of it: parse each field into a typed value during validation and render the CEL from the typed value. `bar_field_name` (`mod.rs:190-203`) already demonstrates the right pattern — it matches on the proto oneof and returns a `&'static str`, so caller input cannot influence the emitted text.

---

### MEDIUM — Firing is level-triggered: nothing suppresses a repeat while the condition holds
`src/bot/alert_bot.rs:88-108` · fix: needs a decision · angle A2

```rust
for (i, result) in results.iter().enumerate() {
    info!("AlertBot: trigger {} fired — {}", i, result.fired);
    if !result.fired { continue; }
```

`rg 'cooldown|debounce|throttle|dedup|idempot|last_fired|last_sent|seen|processed' src/` returns zero hits in the alert subsystem. No edge transition, no cooldown timestamp, no dedup key, no persisted marker anywhere in the fire path, and no proto field for any of the three.

**Trace.** `RiseAbove(AAPL, 150)` at the default 30 s interval. AAPL crosses 150 at 10:00 and stays above it for the rest of the session: **120 notifications an hour, ~780 over one RTH session**, for one price move. At the interval the proto itself suggests (`:183`, *"E.g. `{ seconds: 5 }`"*) it's 720/hour. `TrailingBelow` is the same — the state isn't disarmed by a fire, so `next_state = {'hwm': 150}` reproduces the identical decision next cycle.

**Severity is capped at MEDIUM deliberately.** Whether this is a bug depends on intent I cannot source. The contract says the alert *"fires (dispatches to sink) when any trigger returns `fired: true`"*, which is a level-trigger reading if you take it literally. I have no confirmation from you that edge-triggering is what you want, so this is filed as a contract-shaped observation with the real question in the section below rather than asserted as a defect. If you confirm the intent, it becomes CRITICAL — 780 messages per session is a product-destroying default.

Today it only produces log spam: delivery is a `TODO` (`:105-107`) and there is no Telegram client anywhere in the tree. But this is the semantics the sink will inherit the moment it's wired.

---

## Also found, not ranked

Cut to keep the list at twelve. Correctness first, so what follows is real but either narrower, latent, or hygiene. Anchors so you can pull any of them up:

- **Breakout triggers are unsatisfiable by construction** (`mod.rs:126-132`). The window ends at `context.now`, so it includes the *in-progress* bar, whose `high` already reflects the price being tested — `price > bar_high` can't be true. The proto says *"the last `lookback_bars` **completed** bars"*. Closed-closed bounds also admit `lookback_bars + 1` bars at exact alignment. Latent behind the `reduce_bars` stub, but baked into the CEL this branch emits.
- **`CreateAlert` leaks an unreachable Redis record** if `start_bot` fails (`server/mod.rs:618-627`): metadata is committed first, the caller never receives the `alert_id`, `resume_bots` only revives `Running` bots, and there's no `ListAlerts`. One orphan per failed create.
- **Two concurrent `start_bot` calls spawn two evaluation loops** (`bot_manager.rs:209-213`): the guard reads a `Running` status that is only written asynchronously after the mpsc ack. Two `AlertBot`s with independent state — everything fires twice.
- **A permanently broken alert is invisible.** Status stays `Running`, the only bot metric is a duration histogram recorded identically on the failure path, and the log line (`alert_bot.rs:82`) carries no bot_id. An alert failing 100% of ticks for a week looks healthy and fast on a dashboard.
- **`reduce_bars`'s NaN sentinel is correct but its comment understates the blast radius** (`alert_engine.rs:98-118`). It says "breakout triggers", but `reduce_bars` is also the entire implementation of the `high`, `low` and `bar` baselines — so 4 of 6 `Baseline` variants and 2 of 6 trigger types accept config, return a live `alert_id`, and never fire.
- **`percent_offset` has no documented unit** (`alert.proto:130`). The code assumes a fraction; a client sending `5` for "5%" gets `hwm * (1 - 5)`, a negative threshold, and silence.
- **Dead surface:** `Bar::get_highest_high` (`bar.rs:200`) has zero callers and no `get_lowest_low` sibling; `message Alert` (`alert.proto:242`) has zero consumers and its doc describes a storage layout `AlertBotParams` doesn't use; `BotMetadata.can_trade` is written at `bot_manager.rs:147` and never read (the code re-derives it, as its own comment says), and `update_bot_config` carries the stale flag forward.
- **`bot_evaluation_loop` ignores its `CancellationToken`** (`bot_manager.rs:251`) and `cancel_and_wait_for_all_join_handles` awaits each handle sequentially, so K stuck bots cost K × the timeout at shutdown.
- **Money leaves `BigDecimal` for `f64`** at the one place a money comparison happens (`alert_engine.rs:55,59,86`), and `to_f64().unwrap_or(0.0)` would reproduce finding 1 from a market-data fault. I checked bigdecimal 0.4.10 — the `None` branch is effectively unreachable, so this is shape, not a live trace.
- **`block_in_place` is safe in production** (the runtime is `multi_thread, worker_threads = 20`) **but panics under `#[tokio::test]`**, which defaults to `current_thread`. The first unit test written the obvious way will fail confusingly.
- **Your uncommitted line** at `alert_bot.rs:90` logs `"AlertBot: trigger 0 fired — false"` for every non-firing trigger every cycle, before the `continue` at `:92`, and `:106` logs a near-identical string for real firings. Mechanical.

I also ran the removed-behavior check on `build.rs` — dropping the serde derive for `.poligun.ninniku.bot` is **safe**. `bot_metadata.rs` persists via `prost::Message::encode` + base64, never serde, and no `bot`-package type is touched by any `serde_json` call site. Worth a one-line comment in `build.rs` so nobody re-adds it and hits a confusing error from `prost_types::Struct`.

---

## Questions I couldn't answer from the code

These are the ones where I genuinely can't tell intent from the tree, and each one changes a verdict rather than just being a thing I didn't know.

1. **Should a firing be edge-triggered, cooldown-based, or level-triggered?** Nothing in the contract commits, and there's no proto field for a cooldown or a re-arm. If you confirm edge-triggering is intended, finding 12 goes from MEDIUM to CRITICAL and needs a schema field, not just code.
2. **Is an alert supposed to subscribe to its own market data?** `required_symbols` says the engine does; nothing does. If that's the intent, finding 8 is the difference between "an unwired field" and "the feature does not work for any symbol the user hasn't separately `Subscribe`d" — which is currently the case.
3. **Is per-trigger state meant to survive a restart?** If yes, finding 7 is a data-loss bug and `AlertBotParams` needs a state field. If no, the trailing-stop semantics need to be documented as best-effort, because a stop that silently re-anchors lower after a deploy is worse than one that doesn't exist.
4. **Is `Decimal` validated by the server or by the client?** `well_known_types.proto` says the client is responsible *and* that the type exists to avoid losing precision — but `decimal()` converts to `f64` and substitutes `0.0` on failure. Those three can't all be true. Your answer decides whether finding 1 is fixed at the RPC boundary, in the CEL function, or both.
5. **Is `percent_offset` a fraction (`0.05`) or a percentage (`5`)?** One line of proto comment closes it. Right now either reading produces a plausible-looking alert and one of them never fires.
6. **Are the breakout / high / low / bar baselines meant to ship in this branch?** The `reduce_bars` stub disclosure is in a Rust comment; the proto documents all six baselines as working. If they're WIP, the disclosure belongs in the contract (like `pre_market` has) and roughly a third of this surface moves from "defect" to "disclosed". If they're meant to work, the breakout window arithmetic needs the boundary fix before `get_highest_high` gets wired up.

Answering any of these permanently upgrades the note from my inference to your confirmed intent — which is what the memory below is for.

---

## Proposed memory update

There is no knowledge base for this repo yet (neither `.claude/knowledge/` nor `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/`), so this would seed one — scoped to the one domain this review touched, not backfilled across the repo.

**Where it lives is your call, and creating the directory is the record of the choice:** in-repo (`ninniku/.claude/knowledge/`) means teammates and CI agents get it and it shows up in PR diffs; personal (`~/.claude/projects/.../knowledge/`) means it never touches the repo but nobody else benefits.

**I have written nothing.** `git status` in `ninniku` is unchanged. Below is the diff; say the word and I'll apply it.

Two things to notice about what's in here. Every entry is a **pointer or a question, never evidence** — the evidence in the findings above is code I quoted from the tree this session, so a stale entry can only waste a lookup, never manufacture a finding. And there are **zero `provenance: user` entries**, because you haven't told me any of this yet. The six questions above are recorded as `Q-*` with `asked: never`; when you answer one, it gets deleted and rewritten as an `INV` with your words attached.

````diff
--- /dev/null
+++ .claude/knowledge/INDEX.md
@@
+---
+schema: knowledge/v1
+repo: ninniku
+updated: 2026-07-29
+---
+# Knowledge index
+
+Load this file always. Load a domain file when a changed path matches its globs. Load a
+findings ledger only before finalizing a finding in that domain.
+
+| path globs | domain | claims | last verified |
+|---|---|---|---|
+| `src/alert/**`, `src/bot/alert_bot.rs`, `proto/**/alert/**` | [alerting](domains/alerting.md) | 7 | 2026-07-29 @ b00b1d4+wt |
+
+Findings: [alerting](review/findings/alerting.md) — 12 open, 0 fixed, 1 refuted
+
+## Repo-wide notes
+- Bot metadata is persisted to Redis as **prost + base64**, not serde JSON
+  (`src/bot/bot_metadata.rs`). Schema evolution follows protobuf rules; a removed
+  `serde` derive in `build.rs` is not a persistence change.
+- The process runs one `#[tokio::main(flavor = "multi_thread", worker_threads = 20)]`
+  runtime (`src/main.rs`). `block_in_place` is sound in prod and panics under a default
+  `#[tokio::test]`.
+- Prices are `bigdecimal::BigDecimal` everywhere except the CEL alert engine.
+- No test coverage exists under `src/alert/` or `src/bot/` as of this review.

--- /dev/null
+++ .claude/knowledge/domains/alerting.md
@@
+---
+schema: knowledge/v1
+domain: alerting
+paths: ["src/alert/**", "src/bot/alert_bot.rs", "proto/**/alert/**"]
+updated: 2026-07-29
+head: b00b1d4 (+ uncommitted working-tree edits)
+---
+# Alerting
+
+## Intent
+An Alert is a Bot. `CreateAlert` mints an `AlertBot` whose config holds an
+`AlertDefinition`; each tick every trigger's CEL expression is evaluated and a
+`fired: true` result is meant to dispatch to a Telegram sink. `BuiltInTrigger`s are
+translated to CEL at *evaluation* time, not at create time — so a malformed definition
+is a background log line, not an RPC rejection.
+
+## Lifecycle maps
+
+### MAP-alerting-001 — alert_id IS bot_id, and create always starts
+- kind: lifecycle
+- provenance: code
+- status: active
+- anchor: src/server/mod.rs `async fn create_alert` / src/bot/bot_manager.rs `fn delete_bot`
+- recorded: 2026-07-29 @ b00b1d4
+- verify: `rg -n "Cannot delete a running bot|start_bot" src/bot/bot_manager.rs src/server/mod.rs`
+- claim: `create_alert` calls `create_bot` (persists STOPPED) then `start_bot`; the status
+  becomes RUNNING asynchronously via a `Started` ack. `delete_bot` refuses RUNNING and
+  never sends a Stop. Any review of alert lifecycle must check the *composition*, not the
+  functions separately.
+- matters-because: the create/delete pair is the shape that produces FND-alerting-002,
+  and the async ack is the shape that produces the start/delete races.
+
+### MAP-alerting-002 — per-trigger state is positional, in-memory, and survives config swaps
+- kind: lifecycle
+- provenance: code
+- status: active
+- anchor: src/bot/alert_bot.rs `trigger_states: Mutex<Vec<Option<prost_types::Struct>>>`
+- recorded: 2026-07-29 @ b00b1d4
+- verify: `rg -n "create_bot_from_config" src/` (one caller ⇒ the Bot object outlives a ConfigUpdate)
+- claim: `create_bot_from_config` is called only from `resume_bot`, so `BotEvent::ConfigUpdate`
+  swaps the definition *behind* a live `AlertBot`. `trigger_states` is grow-only, keyed by
+  list position, never persisted. Ask "what happens on reorder / removal / restart" for any
+  change touching triggers.
+- matters-because: decides whether A9-class findings are latent or present-tense. They are
+  present-tense, because `UpdateBotConfig` reaches an alert even though `UpdateAlert` doesn't.
+
+### MAP-alerting-003 — an error or a non-positive interval makes the bot deaf
+- kind: mechanism
+- provenance: code
+- status: active
+- anchor: src/bot/bot_loop.rs `Ok(duration) if duration <= chrono::Duration::zero()`
+- recorded: 2026-07-29 @ b00b1d4
+- verify: `rg -n -A2 "continue;" src/bot/bot_loop.rs`
+- claim: both error arms `continue`, skipping the `tokio::select!` that is the only reader
+  of `BotEvent`. A bot on that path never observes Stop or ConfigUpdate again.
+- matters-because: turns any "returns Err every tick" bug into an unstoppable-task bug,
+  which raises severity by a band.
+
+## Taint sources
+
+### TAINT-alerting-001 — CEL source text is built by `format!` from caller strings
+- kind: taint
+- provenance: code
+- status: active
+- anchor: src/alert/mod.rs `fn translate_built_in_trigger`
+- recorded: 2026-07-29 @ b00b1d4
+- verify: `rg -n "format!\(\"" src/alert/mod.rs`
+- claim: `Decimal.value`, `symbol` and `time_unit` are interpolated unescaped into CEL that
+  `Program::compile` executes. `validate_alert_definition` never descends into a
+  `TriggerConfig`. `bar_field_name` is the counter-example of the correct pattern.
+- matters-because: it is the shared root of the fail-open threshold bug and the
+  compile-error-kills-the-alert bug. See REF-alerting-001 before rating it as security.
+
+## Absence claims  — re-verify every time, never trust the record
+
+### ABS-alerting-001 — no dedup, cooldown, or edge detection in the fire path
+- kind: absence
+- provenance: code
+- status: active
+- anchor: src/bot/alert_bot.rs `for (i, result) in results.iter().enumerate()`
+- recorded: 2026-07-29 @ b00b1d4
+- verify_absence: `rg -n 'cooldown|debounce|throttle|dedup|idempot|last_fired|last_sent|re_arm|edge' src/`
+- claim: zero hits in the alert subsystem. No proto field exists for any of the three.
+- matters-because: caps any repeat-fire finding at MEDIUM until Q-alerting-001 is answered.
+
+### ABS-alerting-002 — nothing subscribes market data for an alert
+- kind: absence
+- provenance: code
+- status: active
+- anchor: proto/poligun/ninniku/alert/alert.proto `repeated string required_symbols`
+- recorded: 2026-07-29 @ b00b1d4
+- verify_absence: `rg -n --glob '!target' 'required_symbols' .`
+- claim: one hit, the declaration. Quote/trade reads are cache-only against Postgres, fed
+  solely by the separate `Subscribe` RPC.
+- matters-because: makes "latest_quote errors" the *normal* path rather than an edge case,
+  which is what turns the abort-on-first-error loop into a CRITICAL.
+
+## Open questions  — inferred, unconfirmed, free to be wrong
+
+### Q-alerting-001 — Edge-triggered, cooldown, or level-triggered firing?
+- proposed answer (inferred, unconfirmed): edge-triggered — notify on the transition into
+  fired, not on every evaluation while it holds.
+- would change: FND-alerting-012 from MEDIUM to CRITICAL, and requires a proto field.
+- asked: never
+
+### Q-alerting-002 — Should CreateAlert subscribe `required_symbols`?
+- proposed answer (inferred, unconfirmed): yes; the proto comment asserts it as current behavior.
+- would change: FND-alerting-008 from "unwired field" to "feature is non-functional by default".
+- asked: never
+
+### Q-alerting-003 — Must per-trigger state survive a process restart?
+- proposed answer (inferred, unconfirmed): yes for trailing water marks; a stop that
+  re-anchors lower across a deploy is a correctness loss, not a cache miss.
+- would change: FND-alerting-007 between a data-loss bug and a documentation gap.
+- asked: never
+
+### Q-alerting-004 — Is `Decimal` validated server-side or client-side?
+- proposed answer (inferred, unconfirmed): server-side; the "no validation" disclaimer
+  predates a type now used for alert thresholds where fail-open inverts a decision.
+- would change: where FND-alerting-001 is fixed, and whether `decimal()` may return a value at all.
+- asked: never
+
+### Q-alerting-005 — Is `percent_offset` a fraction or a percentage?
+- proposed answer (inferred, unconfirmed): a fraction (0.05 == 5%), per the code.
+- would change: whether the fix is a proto comment or a validation range.
+- asked: never
+
+### Q-alerting-006 — Are breakout / high / low / bar baselines in scope for this branch?
+- proposed answer (inferred, unconfirmed): no — the `reduce_bars` NaN stub is intentional WIP.
+- would change: whether ~1/3 of the BuiltInTrigger surface is a defect or a disclosure gap.
+- asked: never

--- /dev/null
+++ .claude/knowledge/review/findings/alerting.md
@@
+# Alerting — findings ledger
+
+## Open
+(FND-alerting-001 … 012 — the twelve findings from the 2026-07-29 review, each with
+severity, angle, anchor, trace and fix clarity. Elided here for diff length; I'll write
+them in full if you approve the seed.)
+
+## Fixed
+(none)
+
+## Won't fix
+(none)
+
+## Refuted (graveyard)
+
+### REF-alerting-001 — "Unvalidated input reaching CEL source is a privilege escalation"
+- reason_class: wrong-model
+- scope: this-site-only
+- re_raised: 0
+- refuted: 2026-07-29 @ b00b1d4
+- reasoning: `TriggerConfig` is a oneof, and the same caller on the same RPC may send
+  `NativeTrigger.expression` — arbitrary CEL, by design. Injection through
+  `BuiltInTrigger` therefore crosses no privilege boundary. **Correct model:** it is a
+  robustness defect (a lone apostrophe permanently kills the alert; a crafted symbol
+  silently changes which instrument is read), not a security finding. The CEL sandbox
+  exposes only `Env::stdlib()` plus six registered functions — no fs, process, or network.
+- guard_anchor: proto/poligun/ninniku/alert/alert.proto `NativeTrigger  native_trigger   = 2;`
+- void_if: `NativeTrigger` is removed from `TriggerConfig`, OR any lower-trust producer of
+  `BuiltInTrigger` appears (a queue consumer, a different auth tier, a frontend-only path),
+  OR an auth interceptor is added that distinguishes the two.
+- note: the underlying taint is still recorded as TAINT-alerting-001 and still has open
+  correctness findings. Refuting the escalation does not refute those.
````

If you'd rather not keep memory at all, say so and I'll drop it — I won't re-ask this session, and I won't write it somewhere else.
