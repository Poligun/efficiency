# Review: `cel-alert` (5 commits, ~1840 lines added vs `main`)

Scope reviewed: the whole branch diff (`main...cel-alert`) plus the three uncommitted working-tree changes. `cargo check --locked` and `cargo clippy` both pass clean — no new warnings from the alert code. Focus below is design and logic, as requested.

**Overall:** the architecture is good. Modelling built-in triggers as sugar that desugars into the native CEL representation is the right call — one evaluation path, one place for bugs. The proto is well documented and thoughtfully versioned. But the feature is not finished end-to-end, and there are several concrete logic bugs that will bite in production. I'd hold the merge for the blockers, or merge behind a flag with the gaps tracked.

---

## Blockers

### 1. An alert can never be deleted

`create_alert` creates the bot and immediately calls `start_bot`, which drives status to `Running` in Redis (`bot_manager.rs:352-361`). `delete_alert` then calls `BotManager::delete_bot`, which begins with:

```rust
if metadata.status == BotStatus::Running as i32 {
    return Err(format!("Cannot delete a running bot: {}", bot_id).into());
}
```

So `DeleteAlert` returns `Internal: Cannot delete a running bot` for every alert that was created normally. The proto comment even states the intended contract:

> `// Each alert runs in its own AlertBot. CreateAlert creates (and starts) the AlertBot; DeleteAlert stops and removes it unconditionally.`

`delete_alert` needs to `stop_bot` first and wait for the `Stopped` ack before deleting. Note `stop_bot` is fire-and-forget over a broadcast channel — the status flips to `Stopped` only when the bot loop acks, so a naive `stop_bot(); delete_bot()` will still race. This needs a real await-for-stop path.

Files: `src/server/mod.rs:602-668`, `src/bot/bot_manager.rs:183-196`.

### 2. `reduce_bars` is a stub, so a third of the trigger surface silently does nothing

`alert_engine.rs:100-118` registers `reduce_bars` as a function that logs a warning and returns `f64::NAN`. That kills, silently:

- `BreakoutAbove` / `BreakoutBelow` (both trigger types depend on it entirely)
- `Baseline::High`, `Baseline::Low`, `Baseline::Bar` (three of the six baselines) — so `RiseAbove` on a bar close is also dead

`validate_alert_definition` (`src/server/mod.rs:682-702`) happily accepts all of these. A user creates a breakout alert, gets a 200 and an `alert_id`, and it never fires. The only signal is a `warn!` line per evaluation per binding — which for a 30s interval is also meaningful log spam.

The NaN-sentinel comment is correct about IEEE 754 comparisons, but it papers over the real problem: **failure is indistinguishable from "condition not met."** Either reject these trigger/baseline types at `CreateAlert` with `unimplemented`, or return an error from `reduce_bars` so the evaluation fails loudly.

Related: `Bar::get_highest_high` was added in `src/postgres/bar.rs:200-250` and is **never called from anywhere**. It's the beginnings of the real implementation, but as landed it's dead code, and there's no `get_lowest_low` counterpart, so it wouldn't be sufficient even if wired up.

### 3. Nothing is ever delivered

`src/bot/alert_bot.rs:105-107`:

```rust
// TODO: deliver via Telegram when Sink support is wired up
info!("AlertBot: trigger {} fired — {}", i, message);
warn!("AlertBot: Telegram notification not yet implemented");
```

Meanwhile `validate_alert_definition` **requires** `sink` to be present. So the API mandates a delivery target it then ignores. Also, the `{{name}}` binding substitution documented on `Sink.TelegramNotification.message_template` is not implemented anywhere — the template is used as a literal string. Combined with #2, an alert created today can neither compute a bar-based condition nor tell anyone about it. Worth being explicit about whether this branch is intended to be user-visible yet.

### 4. Triggers re-fire every evaluation cycle — no edge detection

Once `price >= threshold` becomes true for a `RiseAbove`, it stays true. There is no "fired" latch, no cooldown, no re-arm condition anywhere in `AlertBot::evaluate` or the engine. At the default 30s interval a single crossing produces a notification every 30 seconds, indefinitely, until the user deletes the alert (which they can't — see #1).

This is a design-level gap rather than a typo: the `TriggerResult` protocol has the machinery to express it (the expression could store `{'fired_at': ...}` in `next_state` and gate on it), but neither the built-in translation nor the bot does. For built-in triggers specifically the user has no way to add that themselves. I'd expect either a debounce/cooldown field on `EvalSchedule` or `AlertDefinition`, or edge-detection baked into `translate_built_in_trigger`.

### 5. One bad trigger kills the entire alert

`alert_engine.rs:177-187`:

```rust
let result = evaluate_trigger_config(trigger_config, state, last_eval_time, market_data.clone())?;
```

The `?` aborts the whole loop. `AlertBot` then logs the error and returns without evaluating anything (`alert_bot.rs:79-85`). Consequences:

- One symbol with no cached quote (`latest_quote` returns `Err("no data for symbol")` on `Ok(None)`) disables every other trigger in the alert, including ones on healthy symbols.
- Triggers after the failing index never get their `next_state` updated, so watermarks silently stop tracking while the alert appears alive.

Errors should be isolated per trigger: log/record the failure, produce `fired: false`, and continue.

This interacts badly with #6 below — `latest_quote` reads `get_latest_cached_quote`, which is a Postgres lookup of the latest *cached* quote populated by the market-data subscription pipeline. If the symbol was never subscribed, the row doesn't exist, and the alert is permanently dead on arrival.

### 6. `required_symbols` is accepted and completely ignored

`AlertDefinition.required_symbols` is documented as:

> `// Symbols required across all triggers. The engine subscribes to market data for these symbols once for the whole alert.`

`grep` finds zero uses in `src/`. No subscription is ever created. Given `MarketData::latest_quote/latest_trades` resolve to `get_latest_cached_*` → Postgres reads of subscription-populated tables (`src/alpaca/alpaca_market_data.rs:32-50`, `src/alpaca/market_data/mod.rs:118-130`), **creating an alert on a symbol nobody has subscribed to produces an alert that never fires and only logs.** For native triggers the doc explicitly says this field is the *only* source of symbol information, so there's no fallback.

At minimum `CreateAlert` should reject unsubscribed symbols; ideally it subscribes.

### 7. Client-controlled `Duration` can panic the bot task

`alert_bot.rs:54-58`:

```rust
chrono::Duration::seconds(d.seconds) + chrono::Duration::nanoseconds(d.nanos as i64)
```

`d.seconds` is a client-supplied `int64` from `google.protobuf.Duration`. `chrono::Duration::seconds` **panics** when the value is out of range (roughly `|secs| > i64::MAX / 1000`). `CreateAlert` validates only that `interval` is *present*, not that it's sane. A single `CreateAlert` with `interval { seconds: 9223372036854775807 }` panics the evaluation task.

Same class of issue in `alert/mod.rs:206-213`:

```rust
format!("{}s", lookback_bars * multiplier * unit_seconds)
```

Three client-controlled `i32`s multiplied with no checked arithmetic — overflow panics in debug, wraps in release (producing a nonsensical or negative duration string that then fails CEL compilation forever).

Use `try_seconds` / `checked_mul`, and add range validation in `validate_alert_definition`. Also note `interval` is never checked for positivity: `interval { seconds: 0 }` makes `bot_loop` hit its "non-positive duration" branch, sleep 5s, and log an error forever; `interval { nanos: 1 }` gives you an unthrottled hot loop hammering Postgres.

---

## Should fix

### 8. CEL expression injection via `Decimal.value` and `symbol`

`translate_built_in_trigger` builds CEL source by string interpolation of raw client input:

```rust
let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);
...
format!("latest_quote('{}').ask", symbol)
```

`Decimal` is a string wrapper and the proto comment you added in this branch says outright:

> `// The API will not perform any validation on the format of the string, so it is the responsibility of the client to ensure that it is a valid decimal number.`

Nothing escapes the single quote. A `price.value` of `1') || true || decimal('1` produces a syntactically valid expression that always fires; more interestingly, the injected expression can call `latest_quote('<any symbol>')`, reaching market data outside the alert's declared scope. A quote in `symbol` just yields a permanent compile error.

Blast radius is limited (the CEL context only exposes these few functions, and the caller is already authenticated for the account), but this is unvalidated input flowing into an interpreter. Validate `Decimal.value` parses as a decimal and `symbol` matches an expected charset before interpolation — cheap, and it also gives users a real error at create time instead of a runtime log line.

### 9. `DeleteAlert` will delete non-alert bots

`delete_alert` verifies account ownership (good — better than `DeleteBot`, which checks nothing), but never verifies the target is actually an alert bot. Any stopped trading bot on the same account can be removed through the alert API. Add a `matches!(config.bot_params, Some(BotParams::AlertBotParams(_)))` check and return `not_found` otherwise. `UpdateAlert` will need the same check when implemented.

### 10. The new "one trading bot per account" invariant is bypassable

The rework in `create_bot` (`bot_manager.rs:113-137`) is well-reasoned — the comment about re-deriving `can_trade` rather than trusting the stored field is exactly right for the migration case. But the invariant is only enforced in `create_bot`. `UpdateBotConfig` (`src/server/mod.rs:567-586`) accepts any `BotConfig` for any `bot_id` with no re-check, so:

1. `CreateAlert` (unrestricted — `can_trade == false`)
2. `UpdateBotConfig` that bot into a trading config
3. Two trading bots on one account

`UpdateBotConfig` also does no account-ownership check at all, which is pre-existing but now load-bearing for a security invariant.

Separately: `BotMetadata.can_trade` (new proto field 7) is written but **never read** — the code always re-derives via `bot_can_trade()`. Either read it (with the migration fallback) or drop the field; storing a value you deliberately don't trust is a trap for the next reader.

### 11. Per-trigger state is keyed by list position

`trigger_states: Vec<Option<Struct>>` indexed by position in `AlertDefinition.triggers`. `AlertBot::evaluate` re-reads `bot_config` every cycle, and configs are mutable at runtime via the `ConfigUpdate` event. If a user reorders or removes a trigger, state silently migrates to the wrong trigger — a trailing stop inherits another trigger's high-water mark. The vector also only ever grows (`while states.len() < trigger_count { push(None) }`, duplicated in both `alert_bot.rs:63-65` and `alert_engine.rs:171-173`) so removals leave stale entries.

Key state by a stable per-trigger identifier, or reset state wholesale on config change. Also worth deduplicating the two grow-loops — having the same invariant maintained in two places is how they drift.

### 12. `initial_state` is silently ignored

`NativeTrigger.initial_state` is defined and documented in the proto ("Seed state for the very first evaluation"). Grep finds exactly one occurrence in `src/`: `alert/mod.rs:160`, where the translator sets it to `None`. The engine never reads `trigger.initial_state` — `state` comes only from the `states` vector, which starts as `None`. Any client-supplied seed state is dropped on the floor with no error.

### 13. State round-trip changes integers into floats, breaking arithmetic

`cel_value_to_prost_value` maps `Value::Int` → `Kind::NumberValue(f64)`, and `prost_value_to_cel` maps every `NumberValue` back to `Value::Float`. I checked cel 0.14: comparisons coerce across Int/Float (`objects.rs:697-744`), but **arithmetic does not** — `Adder`/`Multiplier` only handle `(Int, Int)`, `(UInt, UInt)`, `(Float, Float)` and otherwise return `UnsupportedBinaryOperator`.

So the natural native-trigger idiom:

```
next_state: {'count': ('count' in context.state ? context.state['count'] : 0) + 1}
```

works on evaluation 1 (Int + Int) and fails on evaluation 2 with `unsupported binary operator "add"`, because `count` came back as a Float. That's a nasty, non-obvious failure for anyone writing native triggers. Either preserve int-ness through the round-trip, or document that all state numerics are floats and have the translation emit float literals.

Same function's catch-all `_ => Kind::NullValue(0)` silently nulls `Timestamp`, `Duration`, and `Bytes`. Storing a timestamp in state is the obvious way to implement a cooldown (see #4), and it will silently produce `null`.

### 14. `last_eval_time` bookkeeping loses a window and is per-trigger inconsistent

Three related issues:

- `evaluate_native_trigger` calls `Utc::now()` **per trigger** (`alert_engine.rs:23`), so triggers in the same cycle see different `context.now`.
- `AlertBot` sets `last_eval_time = Utc::now()` *after* evaluation completes (`alert_bot.rs:77`), which is strictly later than the `now` the engine used. The gap between engine-`now` and post-eval-`now` is never covered by any `[last_eval_time, now]` window. Once `reduce_bars` is real, that's dropped bars. Capture one `now` per cycle, pass it down, and store *that*.
- `last_eval_time` is advanced even when evaluation errored ("regardless of evaluation outcome"). Deliberate per the comment, but it means a transient DB error permanently skips that window's bars. Worth a second look once bar queries are real.
- On the very first evaluation `last_eval_time` falls back to `now` (`alert_engine.rs:210-212`), making the window zero-width. `Baseline::High/Low` and `Baseline::Bar` will resolve to nothing on the first cycle. Consider a lookback default instead.

---

## Design notes worth considering

**15. `decimal()` is a lie.** `ctx.add_function("decimal", |s| s.parse::<f64>())`. Everything downstream is `f64`. Meanwhile `MarketData` gives you `BigDecimal` and you immediately do `q.ask_price.to_f64().unwrap_or(0.0)`. Two consequences: (a) the branch introduces float rounding into price comparisons in a trading system, which is the thing `Decimal` exists to prevent; (b) `unwrap_or(0.0)` on conversion failure, and the same `unwrap_or(0.0)` in `decimal()` on parse failure, mean a failure silently produces **price = 0.0** — which immediately satisfies every `FallBelow` and every `TrailingBelow` condition. A parse failure should be an `ExecutionError`, not a value that fires the alert. That one is arguably a blocker; I've put it here only because the parse path is currently unreachable for well-formed clients.

**16. Blocking DB I/O from inside CEL functions.** `tokio::task::block_in_place` + `Handle::current().block_on(...)` inside each market-data function. It works on the 20-worker multi-thread runtime, but each alert evaluation occupies a full worker thread for the duration of its Postgres round trips, and there's no memoization — N triggers on the same symbol means N identical queries per cycle. `required_symbols` (#6) exists precisely to enable the better shape: pre-fetch market data async, inject it into the CEL context as plain values, keep evaluation pure and synchronous. That also removes the runtime-flavor coupling.

**17. CEL programs are recompiled every cycle.** `Program::compile` runs per binding and per expression on every evaluation (`alert_engine.rs:122, 135`), and for built-in triggers the whole desugaring re-runs too (`evaluate_trigger_config:157`). Compile once at `CreateAlert` — which has the bonus of turning "invalid expression" into a `400` at create time instead of an error log every 30 seconds forever.

**18. `validate_alert_definition` doesn't validate the triggers.** It checks that `triggers` is non-empty, `interval` is present, and `sink` is present — but not that each trigger has a `trigger_type`, that a `BuiltInTrigger` has a `baseline`, that a `NativeTrigger` compiles, or that the expression returns a map with `fired`. All of those are already checked in the engine and turned into `EngineError` strings; running the translation + compile at create time would surface them as `InvalidArgument`.

**19. `market_hours_filter` is accepted and ignored.** Zero references in `src/`. An alert configured for regular hours only will evaluate 24/7.

**20. `parse_trigger_result` fails open.** A missing or non-bool `fired` key yields `fired: false` via `unwrap_or(false)` rather than an error, so a typo'd expression is indistinguishable from a working one that isn't firing. Given #2 and #6 also fail silently, there are now four independent ways for an alert to be quietly dead. Some kind of per-alert health/last-evaluation status exposed over the API would go a long way.

**21. `lookback_duration` silently defaults unknown units to 60s** (`alert/mod.rs:206-213`) — `"DAY"`, `"WEEK"`, a typo, or an empty string all become minutes. `time_unit` is a free-form `string` in the proto; an enum would make this unrepresentable.

**22. Percent semantics are undefined.** `new_hwm * (decimal('1') - decimal('{pct}'))` assumes `percent_offset` is a fraction (`0.05`), but the field is named "percent". Document it in the proto — a client sending `5` gets `hwm * -4`.

**23. `create_bot("alert", ...)`** gives every alert bot the same `bot_name`. Fine if `bot_name` is purely cosmetic, but it makes `GetBotStatuses` output unreadable once a user has a few alerts.

**24. `CreateAlert` is not atomic.** If `start_bot` fails after `create_bot` succeeds, the RPC returns an error but a stopped orphan bot remains in Redis with an ID the caller never learns — and thanks to #1's inverse, it can at least be deleted. Still worth cleaning up on the failure path.

---

## Unrelated changes riding along

**25. Removing `pattern_day_trader` and `daytrade_count` from `AccountInfo`.** Marking the field numbers `reserved` is exactly right, and I assume this is deliberate cleanup — but it's a breaking API change bundled into a CEL alert branch. `ninniku-fe/src/generated/poligun/ninniku/alpaca/account_info.ts` still declares both fields (lines 44-46, 100-102, 159, 173) and has not been regenerated, so the FE will silently render `patternDayTrader: false` / `daytradeCount: 0` for every account. That's worse than a compile error. Either regenerate the FE in this branch or split this into its own change.

**26. `build.rs` drops the serde derive for `.poligun.ninniku.bot`.** I traced the reason — `AlertBotParams` transitively pulls in `google.protobuf.Struct`/`Value`, which prost-types doesn't derive serde for, so the attribute no longer compiles. Fair. I confirmed nothing currently serde-serializes bot types (`bot_metadata.rs` uses prost `encode` + base64), so this is safe today. But it's an invisible capability removal driven by an unrelated feature; a one-line comment in `build.rs` explaining why would save the next person the same investigation.

**27. Dependency bumps** (~20 crates, `tower-http` 0.6→0.7, `tokio-tungstenite` 0.29→0.30, `redis` 1.2→1.4) are mixed into the same branch, including two commits that are *only* bumps. `tower-http` and `tokio-tungstenite` are both major-version bumps of crates in the request path. These are unrelated to CEL alerts and would be much easier to bisect as a separate PR.

---

## Working-tree changes not yet committed

Three uncommitted modifications — make sure these are intentional before merging:

1. **`src/bot/alert_bot.rs:90`** — a leftover debug line:
   ```rust
   info!("AlertBot: trigger {} fired — {}", i, result.fired);
   ```
   It logs at `info` for *every* trigger on *every* cycle regardless of whether it fired, and the message reads "trigger N fired — false", which is actively misleading in logs. It's also immediately followed by a near-identical log at line 106 for the actually-fired case. This should not ship.
2. **`Cargo.toml`** — `base64` 0.22.1 → 0.23.0, another major bump, on top of the 20 in the committed history.
3. **`Cargo.lock`** — corresponding update.

---

## No tests

The branch adds ~560 lines of intricate string-generating and value-marshalling logic and zero tests. The repo has only two test modules total, so this isn't a regression in convention — but `translate_built_in_trigger` is the single highest-value thing in this codebase to unit test: it's pure (`BuiltInTrigger` → `NativeTrigger`), has no I/O, and covers six trigger types × six baselines. A table-driven test asserting the generated CEL for each combination would have caught the injection issue (#8), the unit-default issue (#21), and would make the `reduce_bars` gap (#2) visible as an explicit `#[ignore]`. `prost_value_to_cel` / `cel_value_to_prost_value` round-trip tests would have caught #13.

---

## What's good

- The desugaring architecture (built-in → native CEL → one evaluator) is the right decision and will pay off.
- `TriggerResult` as a map-returning protocol with room for new keys is a clean, extensible evaluation contract.
- The proto is unusually well commented, including honest "not yet implemented" markers on `MarketHoursFilter`.
- `reserved 7` / `reserved 21` rather than deleting field numbers outright.
- The `can_trade` migration comment ("bots created before field 7 was added decode with the proto default `false`") shows real care about the existing-data path.
- `delete_alert`'s account-ownership check is a genuine improvement over the surrounding `delete_bot`, which has none.
- The `Nullable<Numeric>` comment in `get_highest_high` documents a subtle Diesel gotcha correctly.
- Clean clippy, clean `cargo check`.

---

## Suggested merge path

Fix before merging: #1 (delete is broken), #7 (panic from unvalidated input), #5 (error isolation), and the uncommitted debug log.

Fix or explicitly gate: #2, #3, #4, #6 — these are the difference between "the feature exists" and "the feature works." If the intent is to land the skeleton and iterate, I'd make `CreateAlert` reject the unimplemented trigger/baseline types and unsubscribed symbols outright, so users get an error rather than a silent no-op.

Split out: #25 (`AccountInfo` field removal + FE regeneration) and #27 (dependency bumps).
