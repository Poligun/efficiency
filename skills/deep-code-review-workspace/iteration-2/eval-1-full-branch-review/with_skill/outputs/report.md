# Review: cel-alert → origin/HEAD (merge-base `e85ca8d`)

This branch adds a whole alerting subsystem: a new `poligun.ninniku.alert` proto package, three RPCs, an `AlertBot` bot type, and a CEL evaluation engine that compiles user-supplied expressions at runtime. The design is thoughtful — the `BuiltInTrigger` → `NativeTrigger` translation is a genuinely good idea, and the `can_trade` relaxation is carefully reasoned in its own comment. But the feature does not currently work end to end: **an alert created through `CreateAlert` can never be deleted through `DeleteAlert`**, and three of the six baselines plus both breakout triggers silently never fire because `reduce_bars` is a stub the contract doesn't disclose. Separately, this branch carries a breaking change to `AccountInfo` that has nothing to do with alerting.

**Coverage.** All four aspects were active at `strength: strong` and all four ran — wire contracts (6 files), code API (5 files), business logic (18 files), conventions (3 new files) — plus the surface-consistency pass, which fires when both API aspects are strong. You didn't ask me to skip anything and nothing was skipped for lack of material. Verification is where this run is weak and you should know it: I dispatched 12 verifiers and **only 4 returned** — the other 8 died on upstream `529 Overloaded` errors, not on their findings. So **every finding below not marked `grounded` or `confirmed` is stamped `unverified`**; several are corroborated by two to four independent agents and by my own reading of the code, which raises confidence but is not the same thing as an adversarial check. One candidate finding was refuted and dropped: an agent reported that `duration()` is emitted into CEL but never registered; it is in the crate's stdlib (`cel-0.14.0/src/env.rs:83` → `types::duration::stdlib`), so that would have been a false positive. No knowledge base exists for this repo at `.claude/knowledge/` or in personal space, so nothing was recalled and — since this run had nobody to ask — nothing was written; the proposed seed is at the bottom. I'm reporting 17 items against a soft cap of ~15; eight lower-value observations were demoted to Design notes rather than dropped. No round 2 was run.

---

## Needs a decision before merge

### D1 — `AccountInfo` drops two day-trading fields, and it's not this branch's business (HIGH · needs-decision · grounded)
`proto/poligun/ninniku/alpaca/account_info.proto:31`

`pattern_day_trader` (7) and `daytrade_count` (21) were populated by the server on every `GetAccountInfo` at the merge-base and are now removed. `reserved` is the right ritual — that isn't the problem. The problem is that proto3 scalars have no presence, so any client still built against the old schema decodes `false` and `0`, which for a day-trading app are the *safe-looking* values rather than an error: "not flagged, zero day trades used." I found no hand-written reader in `src/`, in `ninniku-fe/src` outside `/generated/`, or in `analytics/*.py` outside `*_pb2*` — and both generated-client trees are gitignored, so the repo cannot tell you what's actually deployed.

```
-  bool pattern_day_trader = 7;
+  reserved 7; // Was pattern_day_trader

-  int32 daytrade_count = 21;
+  reserved 21; // Was daytrade_count
```

This landed in commit `aad07b3 "Bump dependnecies"`, alongside `Cargo.toml` and `Cargo.lock`. A breaking account-API change riding in a dependency-bump commit inside a CEL-alerting branch is how breaking changes reach production unnoticed.

**Open question.** Why is this in this branch? If the fields are genuinely dead, it wants its own PR with a client-regeneration step. If something replaces them, nothing in the diff shows it. Also worth deciding now: the *numbers* are reserved but the *names* are not — add `reserved "pattern_day_trader", "daytrade_count";` or a future author can reuse the names at new numbers and produce two incompatible JSON shapes across client generations.

### D2 — Alert firing is level-triggered with no cooldown or edge detection (HIGH · needs-decision · unverified)
`src/bot/alert_bot.rs:91`

The notify branch tests the *level* of `TriggerResult.fired`, not the transition into it, and nothing records that a firing already happened (`rg -ni 'cooldown|debounce|throttle|dedup|idempot|last_fired|already_fired' src/ proto/` → no matches). `RiseAbove`/`FallBelow` translate to a pure comparison holding no state at all, so once the condition is true it is true on every subsequent tick.

```rust
            if !result.fired {
                continue;
            }
```

With the proto's own suggested `{ seconds: 5 }` interval, one AAPL crossing at 09:31 that holds for the session produces ~4,700 dispatches. This is latent only because the Telegram sink isn't wired yet — the `fired` computation and the notify loop already run today.

**Open question.** Should a firing be edge-triggered (notify only on false→true), cooldown-limited, or genuinely level-triggered? Whichever you pick needs a home: an armed/fired flag in the per-trigger `next_state` survives a config update but not a process restart, because `trigger_states` is in-memory only.

### D3 — Per-trigger state is keyed by list position, and a config update re-binds it (HIGH · needs-decision · unverified)
`src/alert/alert_engine.rs:171`

`trigger_states` is a `Vec` indexed by position in `AlertDefinition.triggers`, and both grow-loops only extend — nothing shrinks, clears, or re-keys. `TriggerConfig` carries no identifier, so nothing in the type system ties a saved water mark to the trigger that produced it.

```rust
    while states.len() < definition.triggers.len() {
        states.push(None);
    }
```

`UpdateAlert` is unimplemented, but the definition is still replaceable at runtime through the existing `UpdateBotConfig` RPC → `BotEvent::ConfigUpdate` → `bot_loop.rs:58 context.update_bot_config(...)`, and `AlertBot::evaluate` re-reads `context.bot_config()` every tick while keeping its old state vector. Trace: `[0]=TrailingAbove(AAPL, +1.00)`, `[1]=RiseAbove(MSFT)`; after AAPL trades down, `states[0] = {lwm: 180.0}`. Replace the trigger list with `[TrailingAbove(MSFT, +1.00)]` and the MSFT trigger reads `prev_lwm = 180.0` — AAPL's low water mark — so `412.0 >= 181.0` fires immediately and permanently on a trailing stop that should never have armed.

**Open question.** Should `TriggerConfig` gain a stable id so state can be keyed by identity (and state for vanished ids dropped)? Or is the trigger list immutable after create — in which case `UpdateBotConfig` must reject `AlertBotParams` and `UpdateAlert` must define what it does to state?

---

## Findings

### F1 — `DeleteAlert` can never delete an alert that `CreateAlert` made (CRITICAL · scoped · confirmed)
`src/server/mod.rs:664`

`create_alert` calls `create_bot` and then `start_bot`. The evaluation loop's *first* statement is `bot_ack_event_sender.send(BotAckEvent::Started(...))`, which the manager loop turns into `status = Running` in Redis before a client could round-trip. `delete_alert` then calls `delete_bot`, which refuses any bot in that state, and never calls `stop_bot`.

```rust
        self.bot_manager
            .delete_bot(&request.alert_id)
```
```rust
        if metadata.status == BotStatus::Running as i32 {
            return Err(format!("Cannot delete a running bot: {}", bot_id).into());
        }
```

Every alert in steady state answers `DeleteAlert` with `Status::internal("Cannot delete a running bot: <id>")`. The record stays in Redis and keeps evaluating forever; the only escape is the unrelated `UpdateBotStatus` RPC, which the alert contract never mentions. This directly contradicts `ninniku.proto:60-61`: *"CreateAlert creates (and starts) the AlertBot; DeleteAlert stops and removes it unconditionally."*

**Fix.** Have `delete_alert` stop the bot and wait for the `Stopped` ack before calling `delete_bot`, or give `BotManager` a delete-with-stop path. Note `stop_bot` only broadcasts an event, so the ack is asynchronous — either the handler waits or `delete_bot` has to tolerate `Running`.

### F2 — Unvalidated `Decimal` and symbol strings are spliced into compiled CEL source (CRITICAL · scoped · unverified)
`src/alert/mod.rs:32`

`translate_built_in_trigger` builds CEL *source text* by `format!`-interpolating request strings straight inside single-quoted literals — `Decimal.value`, `symbol`, `time_unit`, at eleven sites. `validate_alert_definition` checks only that triggers, interval, and sink are present, and `well_known_types.proto:5-9` now states outright that the API validates nothing about `Decimal`.

```rust
            let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);
```
```rust
    ctx.add_function("decimal", |s: Arc<String>| -> f64 {
        s.parse::<f64>().unwrap_or_else(|_| {
            warn!("decimal(): failed to parse '{}', returning 0.0", s);
            0.0
```

Two distinct consequences, both silent. **The sentinel inverts the comparison:** `price.value = "1,250.00"` (a thousands separator, or `"$1250"`, or a trailing newline) is a valid CEL string literal, so it compiles; at evaluation the parse fails, `decimal()` returns `0.0`, and `180.25 >= 0.0` fires on the first tick and every tick after. The same input on `FallBelow` never fires for the alert's entire life. **A quote changes the program's structure:** `price.value = "0') || (1 == 1"` yields `{'fired': price >= decimal('0') || (1 == 1)}`, which compiles and is unconditionally true — the configured price condition is gone. `symbol = "BRK'B"` yields `latest_quote('BRK'B')`, a compile error that `alert_bot.rs:81-84` logs and swallows, so at a 5s interval the alert emits 720 error lines an hour and never fires while `CreateAlert` already returned 200.

This is not privilege escalation — `NativeTrigger` already lets the same caller submit arbitrary CEL. It's that a rejectable input error was turned into an invisible runtime one.

**Fix.** Stop building source text from user values: parse `Decimal.value` into a number and emit a numeric literal (or bind it as a CEL parameter), and restrict `symbol` to a character class in `validate_alert_definition`. Compiling the translated program once at create time would also convert this whole class of failure into an `InvalidArgument`.

### F3 — `required_symbols` has no reader, so nothing ever subscribes (HIGH · scoped · unverified)
`proto/poligun/ninniku/alert/alert.proto:238`

The field's own comment makes it the mechanism, not a hint: *"The engine subscribes to market data for these symbols once for the whole alert"*, and *"For NativeTrigger, this is the only source of symbol information."* `rg -n required_symbols` over the whole repo returns the proto line and nothing else, and the `MarketData` trait exposes no subscribe operation at all.

```
  // Symbols required across all triggers. The engine subscribes to market
  // data for these symbols once for the whole alert.
  repeated string required_symbols = 4;
```

`latest_quote` resolves to `Quote::get_latest_quote` against Postgres, and the only writer of that table is the poller driven by `subscriptions::get_subscribed_cryptos`. For a symbol not already subscribed through the separate `Subscribe` RPC, `latest_quote` returns `Ok(None)`, which `alert_engine.rs:63-66` converts into a hard `ExecutionError` — the alert never fires, and (per F4) it takes every sibling trigger down with it.

**Fix.** Subscribe `required_symbols` when the AlertBot starts, or delete the field and document that callers must `Subscribe` separately. Four independent agents flagged this one.

### F4 — The first failing trigger aborts every later trigger in the same alert (HIGH · scoped · unverified)
`src/alert/alert_engine.rs:180`

`evaluate_alert_definition` uses `?` inside its per-trigger loop, so the first trigger that errors returns `Err` for the whole alert and higher indices are never evaluated — even though `alert.proto:222-226` declares the triggers independent (*"when any trigger returns TriggerResult{fired: true}"*, *"Each trigger maintains independent state"*).

```rust
        let result =
            evaluate_trigger_config(trigger_config, state, last_eval_time, market_data.clone())?;
```

Errors here are routine, not exceptional: a symbol simply missing from the quote cache becomes an `ExecutionError`. Trace: `triggers: [RiseAbove(TSLA, ask), RiseAbove(AAPL, ask)]` with TSLA uncached — `i=0` errors, `?` returns before `i=1` runs, and an AAPL breach produces no alert on this tick or any tick while TSLA stays uncached. Worse, `states[i]` is mutated in place *inside* the loop, so a lower-index trailing trigger's water mark advances on a tick whose result is then discarded.

**Fix.** Collect per-trigger outcomes (`Vec<Result<TriggerResult, _>>`, or push a non-fired result plus the recorded error) so one trigger's failure doesn't skip the rest, and surface per-trigger failure somewhere a user can see.

### F5 — The `reduce_bars` stub kills three baselines, not just the two breakout triggers (HIGH · scoped · unverified)
`src/alert/alert_engine.rs:116`

The stub is disclosed in a comment and a `warn!` — but not in the contract. Nothing in `alert.proto` marks `Baseline.high`, `Baseline.low`, `Baseline.bar`, `BreakoutAbove`, or `BreakoutBelow` as unsupported, and the same file *does* mark `MarketHoursFilter.pre_market`/`post_market` "Not yet implemented", so the omission reads as an assurance.

```rust
            // NaN is the safe sentinel: all IEEE 754 comparisons against NaN return false,
            // so no trigger fires regardless of direction or baseline type.
            f64::NAN
```
```rust
        Some(BaselineType::High(())) => format!(
            "reduce_bars('{}', 1, 'MINUTE', context.last_eval_time, context.now, 'max', 'high')",
```

Because `translate_baseline` routes `high`, `low`, and `bar` through `reduce_bars`, the dead surface is much wider than the two breakout types — a plain `RiseAbove` on a `bar` baseline is equally dead. A client submits it, gets a 200 with an `alert_id`, and the alert can never fire for any reason they can observe. `src/postgres/bar.rs::get_highest_high` was added in this branch and has no caller, which looks like the first step of the real implementation.

**Fix.** Mark those five surfaces "not yet implemented" in `alert.proto` and reject them in `validate_alert_definition` until `reduce_bars` lands. A `Status::unimplemented` at create time is strictly better than a NaN that looks like a working alert.

### F6 — The Sink is required, delivers nothing, and its documented template syntax doesn't exist (HIGH · scoped · unverified)
`proto/poligun/ninniku/alert/alert.proto:231`

`CreateAlert` *rejects* a definition without a sink, and `bot.proto:41-42` describes the AlertBot as one that "dispatches to the configured Sink when any trigger fires" — with no qualification anywhere in the contract. `rg -i telegram` over `src/`, `Cargo.toml`, and the settings files finds only three lines in `alert_bot.rs`: a TODO and a warning. There is no crate, no token setting, no client.

```rust
            // TODO: deliver via Telegram when Sink support is wired up
            info!("AlertBot: trigger {} fired — {}", i, message);
            warn!("AlertBot: Telegram notification not yet implemented");
```

The template is a second, separate promise: `alert.proto:210-212` documents that binding names are substituted as `{{name}}` and gives a worked example, but the only consumer clones the string verbatim and no substitution code exists anywhere. The TODO covers *delivery*, so templating isn't disclosed even in the implementation — and it can't be added without changing the engine's return shape, since binding values never leave the CEL context (`TriggerResult` carries only `fired`/`next_state`/`message`).

**Fix.** Mark `Sink` not-yet-implemented in the proto, or stop requiring it at `CreateAlert`. For the template: either return the evaluated bindings alongside `TriggerResult` and render before dispatch, or delete the substitution sentence and rely on `TriggerResult.message`.

### F7 — `UpdateBotConfig` bypasses the one-trading-bot rule and leaves `can_trade` stale (HIGH · scoped · unverified)
`src/bot/bot_manager.rs:166`

`bot.proto:18-20` states the invariant as a property of the system — *"At most one trading bot may be registered per account"* — but the check lives only in `create_bot`. `update_bot_config` rebuilds metadata with struct-update syntax, so it neither re-derives `can_trade` nor re-runs the uniqueness check, and `validate_bot_config` accepts any `bot_params` for any `bot_id`.

```rust
        let new_metadata = BotMetadata {
            bot_config: Some(bot_config.clone()),
            ..metadata
        };
```

Trace: account A already has a trading bot. `CreateAlert` on A succeeds correctly (`bot_can_trade` is false for `AlertBotParams`). The client then calls `UpdateBotConfig(alert_id, NoOpBotParams{...})` — no check runs, `can_trade` stays `false`, and A now has two bots the constraint counts as trading. Separately, the concrete `Bot` implementation is chosen once in `create_bot_from_config` and never rebuilt on `ConfigUpdate`, so the still-running `AlertBot` hits its `BotParams` mismatch and errors every 5s forever while reporting `Running`. And note that `BotMetadata.can_trade` is *written* at `bot_manager.rs:147` and read by nothing — the enforcement path deliberately re-derives from `bot_config` instead, so the field on the wire is decorative and can go stale.

**Fix.** Re-run the trading-bot check and recompute `can_trade` inside `update_bot_config`, and reject a config update whose `bot_params` variant differs from the stored one (or restart the bot with a freshly built implementation).

### F8 — `time_unit` is a free-form string where this wire already has a `TimeUnit` enum (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:94`

Three new fields (`:94`, `:154`, `:162`) declare `string time_unit`, while every other bar-interval field on this wire uses `poligun.ninniku.marketdata.TimeUnit` — `ninniku.proto:85`, `ninniku.proto:99`, `marketdata.proto:33`, `marketdata.proto:103`; four occurrences, zero counterexamples before this branch.

```
      string time_unit  = 2; // e.g. "MINUTE"
```
```rust
    let unit_seconds: i32 = match time_unit.to_uppercase().as_str() {
        "MINUTE" => 60,
        "HOUR" => 3600,
        _ => 60,
    };
```

`string` and `enum` are incompatible wire types (LEN vs VARINT), so retyping this after release is wire-breaking, not merely source-breaking — that's the cost, and it's why this is HIGH rather than a style note. The verifier argued for MEDIUM because the "client sends `DAY`, silently gets a 1-minute window" mechanism can't fire while `reduce_bars` is a stub, which is correct; I'm keeping HIGH on the rubric's second clause (an API shape that requires a breaking change to fix later), because the shape ships now and the misbehaviour arrives the moment `reduce_bars` does. Note too that `"HOUR"` isn't representable in the canonical enum today, so the string form already advertises intervals the server can't serve.

**Fix.** Use `poligun.ninniku.marketdata.TimeUnit` and extend the enum if `HOUR` is really needed.

### F9 — Two documented alert fields have no reader at all (MEDIUM · mechanical · unverified)
`proto/poligun/ninniku/alert/alert.proto:53`

`NativeTrigger.initial_state` has exactly two occurrences in the tree: the declaration, and `initial_state: None` in the translator. `evaluate_native_trigger` builds `context.state` solely from the caller-supplied `state` argument.

```
  // Seed state for the very first evaluation, accessible as context.state["key"].
  optional google.protobuf.Struct initial_state = 4;
```
```rust
    let state_map = state
        .map(prost_struct_to_cel_map)
        .unwrap_or_else(|| Value::Map(Map { map: Arc::new(HashMap::new()) }));
```

A `NativeTrigger` author who seeds `{"hwm": 250.0}` and writes the `'hwm' in context.state ? ... : ...` guard the built-ins use gets the un-seeded branch — the trailing stop arms at the current price instead of 250.0, silently. The translator's own workaround is the tell: it can't use `initial_state` for `water_mark` and inlines a fallback expression into a binding instead.

`EvalSchedule.market_hours_filter` and `MarketHoursFilter.regular_hours` are the same shape with a sharper edge: the message explicitly discloses that `pre_market`/`post_market` are unimplemented, which reads as an assurance that `regular_hours` *is*. It isn't — zero references outside the proto. An equities alert configured `regular_hours: true` evaluates at 03:00 against a stale cached quote, which is exactly what the filter was set to prevent.

**Fix.** For `initial_state`, one line: `state.or(trigger.initial_state.as_ref())` when building the context map, matching the doc's stated precedence. For `market_hours_filter`, either gate evaluation on the window or mark it not-yet-implemented the way its siblings already are.

### F10 — An out-of-range eval interval panics the bot task and leaves an undeletable zombie (MEDIUM · mechanical · unverified)
`src/bot/alert_bot.rs:55`

`validate_alert_definition` checks only that `eval_schedule.interval` is *present*, never that it's in range, and prost doesn't enforce `google.protobuf.Duration`'s documented plus/minus 315,576,000,000-second bound.

```rust
                chrono::Duration::seconds(d.seconds)
                    + chrono::Duration::nanoseconds(d.nanos as i64)
```

`chrono::Duration::seconds` panics when `|seconds| > i64::MAX / 1000`. The panic happens inside a spawned task whose `JoinHandle` is only polled in `cancel_and_wait_for_all_join_handles` at shutdown (`src/tasks.rs:45-49`), so nothing observes it: the task dies without sending `Stopped`, Redis keeps `status = Running`, `GetBotStatuses` reports the alert healthy, F1 makes it undeletable, and `resume_bots` re-spawns and re-panics it on every restart. A client that filled the field in nanoseconds is enough to trigger it.

**Fix.** Bound the interval in `validate_alert_definition` (reject non-positive and anything past a sane ceiling) and use `chrono::Duration::try_seconds` rather than the panicking constructor.

### F11 — The new alert module signals failure with `String` (MEDIUM · mechanical · grounded)
`src/alert/alert_engine.rs:13`

Every other fallible function under `src/` returns `Box<dyn Error + Send + Sync>` — 125 occurrences across 34 files, with one free-function counterexample (`ResolutionError` at `src/accounts/mod.rs:27`). The `type Error = String` occurrences elsewhere are all `TryFrom`/`TryInto` associated types, a different position.

```rust
type EngineError = String;
```

Flattening at this boundary destroys the source error, so the only consumer can't tell "Postgres is down" from "this CEL expression will never compile" and treats both identically — `error!` and retry at the same cadence, forever. That matters directly for F2 and F3, where a permanent failure is retried like a transient one. Both aliases also lack `pub` while appearing in `pub fn` signatures, so no caller outside the module can name the type.

**Fix.** Return `Box<dyn Error + Send + Sync>`, matching the `MarketData` trait these functions consume and the `Bot::evaluate` they feed.

### F12 — `UpdateAlert` is documented as a replace and returns unimplemented (MEDIUM · scoped · unverified)
`proto/poligun/ninniku/ninniku.proto:67`

The service comment describes it without caveat — *"Replace the AlertDefinition of an existing alert"* — and `UpdateAlertRequest` carries a full definition.

```rust
        Err(Status::unimplemented("UpdateAlert not yet implemented"))
```

The disclosure lives only in the Rust, so any client generated from this `.proto` exposes an operation that can only fail. There is no `GetAlert` or `ListAlerts` either, so a caller has no supported way to change an alert other than delete-and-recreate — which loses trigger state, changes the `alert_id`, and (per F1) doesn't work.

**Fix.** Add `// Not yet implemented.` to the RPC comment, matching what `MarketHoursFilter` already does, and implement it before the API is published.

### F13 — The proto's own `NativeTrigger` example cannot be evaluated (MEDIUM · scoped · unverified)
`proto/poligun/ninniku/alert/alert.proto:46`

The field is documented as *"CEL expression returning TriggerResult"* with a worked example using CEL message-construction syntax:

```
  //   TriggerResult{
  //     fired: price <= new_hwm - decimal('1.00'),
  //     next_state: {'hwm': string(new_hwm)}
  //   }
```
```rust
    let map = match value {
        Value::Map(ref m) => m,
        _ => {
            return Err(format!(
                "Expression must return a map with 'fired' key, got: {:?}",
                value
            ))
```

The engine never registers the `TriggerResult` proto type with the CEL context and `parse_trigger_result` accepts only a bare `Value::Map`. The example also stores state as `string(new_hwm)` while the built-in translator stores floats and feeds them to `max_decimal(a: f64, b: f64)`. A user who copies the documented example — the only guidance there is for the feature's main extension point — gets a compile or type error at every evaluation, and per F2 that error is logged and swallowed. Worth noting that `fired` is read with `.unwrap_or(false)`, so a wrong type there produces no error at all, just an alert that never fires.

**Fix.** Rewrite the example as the map form the engine actually accepts, and say explicitly that state values are numbers.

### F14 — `last_eval_time` advances after a failed evaluation, skipping that window forever (MEDIUM · scoped · unverified) · **latent** until `reduce_bars` is implemented
`src/bot/alert_bot.rs:77`

`last_eval_time` is the low end of the `[last_eval_time, now]` window the `high`/`low`/`bar` baselines scan, and it advances unconditionally — the comment states the choice outright.

```rust
        // Update last_eval_time regardless of evaluation outcome
        *self.last_eval_time.lock().await = Some(Utc::now());
```

A failed evaluation therefore consumes its window without examining it. Two more boundary problems sit on the same value: the low end is sampled *after* the evaluation while the high end (`now`) is sampled at the *start* of the next one, so the evaluation's own duration is permanently uncovered; and on the first tick `last_eval_time` is `None` and falls back to `now`, producing a zero-width window. Trace at a 60s interval: a tick at 10:00:00 errors, `last_eval_time` still moves to 10:00:00.2, and the 09:59-10:00 bar is never scanned by any evaluation — a session high printed in that minute cannot fire the alert.

**Fix.** Advance `last_eval_time` only on success, set it to the `now` used as the window's high end rather than a fresh `Utc::now()`, and seed the first window from `now - interval`.

---

## Design notes

Opinions, labelled as such — no verification was run on any of them.

- **Nothing compiles a trigger until its first evaluation.** All four public functions in `src/alert/` require an `Arc<dyn MarketData>` and compile inline, so there's no way to check a trigger without a live market-data handle. `validate_alert_definition` consequently can't do more than presence checks. A `validate(&NativeTrigger)` entry point that compiles without evaluating would let `CreateAlert` reject a syntax error with `InvalidArgument` instead of a log line — and it's most of the fix for F2.
- **`message Alert` is unreferenced, and its comment contradicts `AlertBotParams`.** It claims to be the "full alert record stored in AlertBotParams", but `AlertBotParams` holds a bare `AlertDefinition` and no RPC returns an `Alert`.
- **`BarField.field` is an enum spelled as a `oneof` of six `google.protobuf.Empty` arms.** This repo models closed sets with enums — 16 of them across 6 proto files, no prior `oneof`-of-`Empty`. `Baseline.baseline_type` is justified (its `bar` arm carries a payload); `BarField.field` isn't.
- **`build.rs` silently drops serde derives from the whole `.poligun.ninniku.bot` package.** Almost certainly forced rather than chosen — `bot.proto` now imports `alert.proto`, so `AlertBotParams` transitively contains `prost_types::Struct`, which isn't `Serialize`. Nothing in-repo relied on the derives (`bot_metadata.rs` persists via prost + base64), so this costs nothing today; it's worth a comment so the next person doesn't spend an afternoon on it.
- **The trigger-count invariant is expressed in three places and truncation in none** — `AlertBot::new`, `AlertBot::evaluate`, and `evaluate_alert_definition` each pad the vector. The constructor argument is load-bearing only until the first tick.
- **`pub mod alert_bot;` exports a module with nothing publicly reachable** — `AlertBot` and its `new` are `pub(super)`, matching the five sibling modules declared private `mod`. The two that *are* `pub` each export a trait consumed from outside the directory.
- **`translate_built_in_trigger` takes `BuiltInTrigger` by value but only reads it**, so its single caller deep-clones the whole message every evaluation cycle. It also recompiles every binding and the main expression on every tick; a compiled-program cache keyed by expression text is the obvious next step.
- **`cargo fmt` wasn't run.** `mod alert;` and `pub mod alert_bot;` are appended out of order in `src/main.rs` and `src/bot/mod.rs`; rustfmt's `reorder_modules` owns this, and `.cursor/rules/rust_rules.mdc` already asks for a `cargo fmt` pass at wrap-up. Not a review finding — just a signal the wrap-up checklist was skipped, which is also why I didn't file anything else a formatter or clippy would catch.

## Could not resolve

- **8 of 12 verifiers died on upstream `529 Overloaded` errors.** Findings D2, D3, F2, F3, F4, F5, F6, F7, F9, F10, F12, F13 and F14 were never adversarially checked. Most are corroborated by two to four independent agents and I traced F1, F4, F7 and the declared-surface greps myself, but corroboration is evidence a finding is *real*, not that it's been attacked. Re-running verification on F2, F5 and F10 in particular would settle them: F2 depends on the CEL crate's string-literal lexing, F5 on how `Value::Float(NAN)` compares inside that crate (and whether a NaN water mark gets persisted into `next_state`), and F10 on whether `chrono` 0.4.45's `Duration::seconds` genuinely panics rather than saturating.
- **Whether D1 is CRITICAL or HIGH rests on state this repo can't see.** Both generated-client trees are gitignored, there's no CI config and no deploy manifest, so nothing here can tell you whether a client built against the old `AccountInfo` schema is actually running. If one is, that finding is CRITICAL.

---

## Convention ledger

For transparency, since convention findings are only as good as their counts:

| Rule | Support | Counterexamples | Verdict |
|---|---|---|---|
| Fallible functions return `Box<dyn Error + Send + Sync>` | 125 across 34 files | 1 (`ResolutionError`, `src/accounts/mod.rs:27`) | established -> F11 |
| Items internal to `src/bot/` use `pub(super)` | 10 across 5 files | 0 | established -> **new code complies** |
| Domain modules export free functions as plain `pub fn` | 4 | 0 | established -> complies |
| Closed sets on the wire are `enum`s | 16 across 6 files | 0 | established -> design note |
| Bar intervals use `marketdata.TimeUnit` | 4 | 0 | established -> F8 |
| Unit tests in `#[cfg(test)]` modules | 2 of 49 files | — | **absent** — "add tests" is a project decision, not a finding |
| `mod` declarations alphabetized | 5 | 1 | established but **formatter-owned** — excluded |

## Proposed knowledge-base seed (nothing was written)

No knowledge base exists at `ninniku/.claude/knowledge/` or in personal space, and this run had nobody to ask which you'd prefer, so nothing was created. If you want one, the entries worth keeping from this review are: `src/alert/mod.rs` is a taint sink (every `BuiltInTrigger` variant becomes `format!`-built CEL source); `AlertBot.trigger_states` is positional, process-local, and mutable at runtime via `UpdateBotConfig`; `alert_id == bot_id` and the alert lifecycle is layered on the bot lifecycle with delete gated on `status`; and an absence claim for firing deduplication with its re-verification grep. Say the word and I'll write them to whichever location you prefer — in the repo (committed, visible to teammates and CI agents) or in personal space (private).

---

I can post this to GitHub as a PR review if you want it there — inline comments for the committed anchors, and a summary section for anything in `src/bot/alert_bot.rs`, `Cargo.toml`, or `Cargo.lock` that's still in your working tree. I'll show you exactly what would be posted first.
