## Review: `cel-alert` — CEL-based alert engine, AlertBot, and the CreateAlert/DeleteAlert RPCs

The evaluation logic itself is mostly sound; what's off is everything *around* one evaluation. Three things would change your plan: **a trigger that fires keeps firing on every tick with no dedup anywhere in the tree**, **`decimal()` swallows a parse failure and returns `0.0`, which flips `price >= threshold` to permanently-true and `price <= threshold` to permanently-false**, and **`DeleteAlert` can never succeed on an alert that `CreateAlert` just started**, because `delete_bot` refuses `Running` bots and `create_alert` starts the bot before returning. Several of the worst ones are latent behind the `reduce_bars` stub and the un-wired Telegram sink — they're written into the code and become live the day those land, so I've marked each one rather than discounting it.

**Coverage.** Behavior model built from `alert.proto`, `alert_engine.rs`, `alert/mod.rs`, `alert_bot.rs`, `bot_loop.rs`, `bot_manager.rs`, `server/mod.rs`. `scope_detect.py` reports `code_lines: 1215` (1112 lines of `Cargo.lock` churn excluded), above the 400-line inline threshold, so A1 (lifecycle) and A10 (concurrency) ran as one read-only subagent and A6 (declared surface) as another; A2, A3, A4, A5, A7, A8, A9 ran inline where holding the whole model matters most. All ten angles ran — A7 gated in (CEL source built by `format!`), A8 (i32/i64 arithmetic on wire values), A9 (positional trigger state), A10 (`block_in_place`, `Mutex`, `tokio::spawn`). No knowledge base exists at `.claude/knowledge/` or `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/`, so nothing was recalled; a seed is proposed at the end.

Cut for length (verified, not written up): `get_highest_high`'s SQL window is inclusive at both ends (`start_time >= $6 AND start_time <= $7`, `src/postgres/bar.rs:216-217`) so consecutive windows double-count the boundary bar — currently harmless, it has zero callers; `create_alert` leaves an orphaned Redis row if `start_bot` fails after `create_bot` succeeded, with a `bot_id` the client never receives (`src/server/mod.rs:618-629`); `delete_alert` checks account ownership but not bot *type*, so it will delete a non-alert bot on the same account (`src/server/mod.rs:659-662`).

Refuted during trace-writing, so not reported: I expected the `reduce_bars` NaN sentinel to poison the trailing-stop watermark permanently. It doesn't — `max_decimal` is `a.max(b)`, and Rust's `f64::max` returns the *other* operand when one side is NaN, so a real price recovers the watermark the moment `reduce_bars` returns one. The comment at `alert_engine.rs:114-115` is correct.

---

## Needs a decision before merge

### CRITICAL — A fired trigger re-fires on every tick, forever
`src/bot/alert_bot.rs:89-108` · fix: needs a decision · **latent** until the Telegram sink is wired (`warn!("AlertBot: Telegram notification not yet implemented")`, `alert_bot.rs:107`)

`evaluate` is level-triggered: it notifies for every result where `fired == true`, with no edge detection, no cooldown, and no persisted "already notified" marker. `TriggerResult` has no field for one, `EvalSchedule` has no cooldown key, and nothing in the tree implements one:

```
$ rg -i 'cooldown|debounce|throttle|dedup|idempot|last_fired|last_sent|seen' src/ proto/
(no matches)
$ rg -n 'prev_fired|was_fired|fired_at' src/ proto/
(no matches)
```

The proto's own wording is edge-shaped — `RiseAbove` is documented as "Fires when price rises above (water_mark + offset)" (`alert.proto:125`), and *rising above* is a crossing, not a state.

**Trace.** `RiseAbove{price: "100"}` on AAPL with `eval_schedule.interval = {seconds: 5}`. AAPL opens at 105 and stays there all session. Every 5 s the expression `{'fired': price >= decimal('100')}` evaluates true → 720 notifications per hour, 4,680 over a 6.5-hour session, and it resumes tomorrow. Nothing survives a restart either: `trigger_states` and `last_eval_time` are in-memory `Mutex` fields (`alert_bot.rs:13,15`), so a redeploy re-arms whatever suppression you add unless it's persisted.

**Fix.** This needs your call on semantics before an implementation, and the two answers produce different code. If firing is meant to be **edge-triggered**, the mechanism already exists — carry a `fired` bit in `TriggerResult.next_state` and gate the notification on `!prev_fired && fired`, which costs one field and no new proto. If it's meant to be **level-triggered with suppression**, that's a new `cooldown` duration on `EvalSchedule` plus a persisted `last_notified_at`, and it has to survive process restarts to be worth anything.

---

## Findings

### CRITICAL — `decimal()` returns 0.0 on a bad string, inverting the comparison
`src/alert/alert_engine.rs:31-36` · fix: scoped

The CEL `decimal` function substitutes `0.0` for any string `f64::parse` rejects, and only logs a warning. Every `BuiltInTrigger` threshold goes through it. Nothing upstream validates the string — `validate_alert_definition` (`src/server/mod.rs:682-701`) checks only that `triggers` is non-empty, `interval` is present, and `sink` is present, and `Decimal`'s own contract disclaims validation outright: *"The API will not perform any validation on the format of the string"* (`proto/poligun/ninniku/well_known_types.proto:5-8`).

```rust
    ctx.add_function("decimal", |s: Arc<String>| -> f64 {
        s.parse::<f64>().unwrap_or_else(|_| {
            warn!("decimal(): failed to parse '{}', returning 0.0", s);
            0.0
        })
    });
```

**Trace.** A client sends `RiseAbove{price: {value: "1,250.00"}}` — a thousands separator, the single most common way a human writes that number. `"1,250.00".parse::<f64>()` fails → `0.0` → the generated expression `{'fired': price >= decimal('1,250.00')}` becomes `price >= 0.0`, true for every real quote → the alert fires on the first tick and never stops. The inverse is in the same function: `FallBelow{price: {value: "1,250.00"}}` becomes `price <= 0.0`, false for every real quote → the alert is silently dead for its entire life and the only trace is a `warn!` line. One typo produces either an unstoppable alert or an alert that can never fire, and the user cannot tell which from the API.

**Fix.** Make `decimal()` return `Err(ExecutionError::function_error(...))` like `latest_quote` does, *and* parse-validate every `Decimal` in `validate_alert_definition` so the failure lands at `CreateAlert` with an `InvalidArgument` rather than at evaluation time. The second half matters more: a runtime error here trips the batch abort described two findings down.

---

### HIGH — `DeleteAlert` can never succeed on an alert `CreateAlert` started
`src/bot/bot_manager.rs:190-193` · fix: mechanical

`create_alert` creates the bot and then starts it before returning (`src/server/mod.rs:618-629`), so every alert reaching the client is `Running`. `delete_bot` refuses exactly that:

```rust
        if metadata.status == BotStatus::Running as i32 {
            return Err(format!("Cannot delete a running bot: {}", bot_id).into());
        }
```

`delete_alert` (`src/server/mod.rs:641-668`) calls straight into it with no stop first. The service contract says the opposite in two places: *"DeleteAlert stops and removes it unconditionally"* (`proto/poligun/ninniku/ninniku.proto:61`) and *"Stop and delete an alert's AlertBot"* (`:68`).

**Trace.** `CreateAlert` → `alert_id = "a1"`, status `Running`. `DeleteAlert{alert_id: "a1"}` → `Status::internal("Cannot delete a running bot: a1")`. The client has no `StopAlert` RPC; the only escape is reaching into the *bot* API with `UpdateBotStatus(a1, Stopped)` and then retrying — a bot_id the alert API never told them was a bot_id. The one window where delete works is the race between `start_bot` returning and `bot_manager_loop` writing `Running` on the `Started` ack (`src/bot/bot_manager.rs:352-360`), which is worse than it never working.

**Fix.** Have `delete_alert` call `stop_bot` and wait for the `Stopped` ack before `delete_bot`, or give `delete_bot` a stop-then-delete path. Either way the proto comment and the code agree afterwards.

---

### HIGH — One trigger's missing market data disables every other trigger in the alert
`src/alert/alert_engine.rs:180` · fix: scoped

`evaluate_alert_definition` propagates with `?` inside the loop over triggers, so the first failure abandons the rest of the batch. Two things make that failure routine rather than exceptional: `latest_quote` converts *absence* into an error (`Ok(None) => Err(ExecutionError::function_error("latest_quote", format!("no data for symbol: {}", symbol)))`, `alert_engine.rs:63-66`), and nothing subscribes to market data at all (next finding). The contract states the opposite of abort-on-first: *"The alert fires (dispatches to sink) when any trigger returns TriggerResult{fired: true}. Each trigger maintains independent state across evaluations."* (`alert.proto:223-226`).

```rust
        let result =
            evaluate_trigger_config(trigger_config, state, last_eval_time, market_data.clone())?;
```

**Trace.** An alert with `triggers[0]` on a delisted or mistyped symbol and `triggers[1]` a working `RiseAbove` on AAPL. Every tick: trigger 0 → `latest_quote` → `Ok(None)` → `Err` → `?` → `evaluate_alert_definition` returns `Err` → `alert_bot.rs:81-84` logs `error!` and returns `Ok(interval)`. Trigger 1 is never evaluated, for the life of the alert. Two side effects compound it: any `states[i]` already written earlier in the aborted pass stays written (`alert_engine.rs:182-184`), so state advances for the triggers that ran and not the ones that didn't; and the failure is invisible — `BotStatus` has only `Running` and `Stopped` (`rg 'BotStatus::' src/`), so the alert reports healthy forever while evaluating nothing.

**Fix.** Collect per-trigger results instead of `?`-ing out: give `TriggerResult` an error variant (or return `Vec<Result<TriggerResult, _>>`) so one dead symbol degrades one trigger. Separately, decide whether "no quote yet" should be an `Err` at all — an empty/absent result that the expression can test is the more useful shape.

---

### HIGH — `required_symbols` has no consumer; nothing subscribes to market data
`proto/poligun/ninniku/alert/alert.proto:238` · fix: scoped

The field is documented as the thing that makes the whole feature work: *"Symbols required across all triggers. The engine subscribes to market data for these symbols once for the whole alert. ... For NativeTrigger, this is the only source of symbol information since CEL expressions are opaque at parse time."* (`alert.proto:233-237`). There is no reader.

```
$ rg -w 'required_symbols' /Users/yuhanzhao/GitHub/ninniku/src /Users/yuhanzhao/GitHub/ninniku/proto
proto/poligun/ninniku/alert/alert.proto:238:  repeated string required_symbols = 4;
```

Nor is there anything to call: the `MarketData` trait (`src/bot/market_data.rs:6-24`) exposes only `latest_bar`, `latest_quote`, `latest_trades` — three point queries, no subscribe. Every `subscribe` in the repo belongs to the Alpaca crypto websocket or a tokio broadcast channel; none is reachable from alert code.

**Trace.** A client creates a `NativeTrigger` alert with `required_symbols: ["AAPL"]` and a CEL expression calling `latest_quote('AAPL')`. Nothing subscribes AAPL. Whether `latest_quote` returns data depends entirely on whether some *other* bot happens to have subscribed the same symbol. When it returns `Ok(None)`, the previous finding turns that into a permanent silent outage for the whole alert. As shipped, an alert on a symbol nobody else is watching never evaluates successfully and never says so.

**Fix.** Either wire `required_symbols` into a subscription at `create_bot`/`resume_bot` time and tear it down at delete, or — if `latest_quote` is genuinely meant to fetch on demand — correct the proto comment, because right now it promises a mechanism that does not exist. See the questions section; I can't tell which you intended.

---

### HIGH — Trigger state is positional and grow-only, so a config update rebinds it
`src/bot/alert_bot.rs:62-65` · fix: scoped

`trigger_states` is *"Per-trigger CEL state, indexed by trigger position in `AlertDefinition.triggers`"* (`alert_bot.rs:12`), and the only reconciliation is a grow-only loop:

```rust
        let mut states = self.trigger_states.lock().await;
        while states.len() < trigger_count {
            states.push(None);
        }
```

A config update does not rebuild the bot. `bot_loop.rs:55-60` handles `BotEvent::ConfigUpdate` by calling `context.update_bot_config(bot_config).await`, which swaps the config inside the shared `RwLock` (`bot_context.rs:34-37`) — `create_bot_from_config` is never called again (`rg create_bot_from_config src/` → only the declaration and `bot_manager.rs:241`). Same `AlertBot`, same `Vec`, new trigger list. This is live today: `UpdateAlert` is unimplemented, but `UpdateBotConfig` (`src/server/mod.rs:567-586`) accepts any `BotConfig` including `AlertBotParams` and does no type check.

**Trace.** An alert with `triggers[0] = TrailingBelow{AAPL, price_offset: "1.00"}` and `triggers[1] = RiseAbove{TSLA}`. After three hours `states[0] = {'hwm': 187.40}`. The user calls `UpdateBotConfig` with `triggers = [TrailingBelow{NVDA, price_offset: "1.00"}]`. Next tick, index 0 is NVDA but the state is AAPL's: `'hwm' in context.state` → true → `prev_hwm = 187.40` → `new_hwm = max_decimal(120.0, 187.40) = 187.40` → `fired: 120.0 <= 186.40` → **true immediately**, a trailing-stop alert on NVDA computed from AAPL's high-water mark. Shortening the list is the same bug in the other direction: `states` never shrinks, so a later re-lengthening re-attaches whatever was left at that index.

**Fix.** Key state by something stable rather than position — a `trigger_id` on `TriggerConfig`, or a hash of the trigger's canonical bytes — or clear `trigger_states` and `last_eval_time` whenever the config changes. Clearing is the smaller change and is correct, just lossier.

---

### HIGH — Unvalidated client strings are interpolated into CEL source
`src/alert/mod.rs:32` · fix: scoped

`translate_built_in_trigger` builds the CEL program with `format!`, splicing `Decimal.value` and `symbol` straight in, and `Program::compile` then parses the result. Twelve sites do this (`mod.rs:32,41,52,55,61,68,88,90,96,103,127,147` plus the baselines at `:168-184`); the representative one:

```rust
            let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);
```

Neither value is validated anywhere on the path — `validate_alert_definition` doesn't look at them, and `Decimal`'s contract explicitly disclaims validation (`well_known_types.proto:5-8`).

**Trace.** Two, and the accidental one is the one that will actually happen. *(a)* A client sends `price.value = "1'250.00"` (Swiss/Italian digit grouping, or just a stray keystroke). The generated source is `{'fired': price >= decimal('1'250.00')}`, `Program::compile` fails at `alert_engine.rs:135-136`, the error propagates through the `?` at `:180`, and — per the batch-abort finding above — the *entire alert*, all triggers, evaluates nothing on every tick for the rest of its life, logging one line each time. *(b)* Deliberately: `price.value = "0') || true || decimal('0"` yields `{'fired': price >= decimal('0') || true || decimal('0')}`; `||` binds looser than `>=` and short-circuits, so `fired` is unconditionally true. Symbol is splicable the same way into `latest_quote('{}')`, letting a `BuiltInTrigger` issue quote lookups for symbols outside its own `symbol` field.

**Calibration, honestly:** this is *not* a privilege escalation. `NativeTrigger.expression` already accepts arbitrary CEL from the same caller by design, so (b) grants nothing the API doesn't already offer. The severity is for (a) — a plausible input producing a permanent, silent, whole-alert outage.

**Fix.** Parse `Decimal.value` into a number in the translator and format the number back out (which also fixes the previous finding at the same time), and validate `symbol` against a character allowlist. Splicing a parsed value is safe; splicing the raw string is not.

---

### HIGH — First evaluation, and every restart, uses a zero-width time window
`src/alert/alert_engine.rs:210-212` · fix: scoped · **latent** until `reduce_bars` is implemented

When there's no previous evaluation, `build_context_map` substitutes `now` for `last_eval_time`:

```rust
    let last_eval_val = last_eval_time
        .map(|t| Value::Timestamp(t.with_timezone(&utc_offset)))
        .unwrap_or_else(|| Value::Timestamp(now.with_timezone(&utc_offset)));
```

`Option::None` here means *"no history"*; the fallback silently converts it to *"zero elapsed time"*, and those are not the same statement. Every `High`, `Low`, and `Bar` baseline queries exactly that window — `reduce_bars('{}', 1, 'MINUTE', context.last_eval_time, context.now, 'max', 'high')` (`src/alert/mod.rs:172-184`).

**Trace.** An alert with a `High` baseline is created at 09:31:00. First tick: `last_eval_time` is `None` → `context.last_eval_time == context.now == 09:31:00` → `reduce_bars(sym, 1, 'MINUTE', 09:31:00, 09:31:00, 'max', 'high')` — a window containing at most the single bar starting exactly on the second, and against `get_highest_high`'s `start_time >= $6 AND start_time <= $7` almost certainly nothing. The trigger cannot fire on its first evaluation regardless of the market. This is not a one-time cost: `last_eval_time` is an in-memory `Mutex<Option<...>>` (`alert_bot.rs:15,22`), so every process restart resets every alert to `None` and reproduces it.

**Fix.** Keep `last_eval_time` as an absent value in the CEL context and make `reduce_bars` treat an absent lower bound as "the current bar" (or as an explicit lookback), rather than defaulting it to `now`. Whatever the rule is, it should be one the expression author can observe, not a silent substitution.

---

### HIGH — `last_eval_time` advances even when evaluation failed, skipping that window forever
`src/bot/alert_bot.rs:76-77` · fix: scoped · **latent** until `reduce_bars` is implemented

```rust
        // Update last_eval_time regardless of evaluation outcome
        *self.last_eval_time.lock().await = Some(Utc::now());
```

The comment says this is deliberate, so I'll state the consequence rather than assume it was an oversight. `context.last_eval_time` is the *low end of a data window*, not a health timestamp — the `High`/`Low`/`Bar` baselines read `[context.last_eval_time, context.now]` (`src/alert/mod.rs:172-184`). Advancing the low end past a window whose contents were never examined means those contents are never examined by anything, ever.

**Trace.** `interval = {seconds: 60}`, a `High`-baseline `RiseAbove`. At 10:05:00 the quote fetch for another trigger in the same alert errors (see the batch-abort finding) → `evaluate_alert_definition` returns `Err` → no trigger is evaluated → line 77 sets `last_eval_time = 10:05:00` anyway. The 10:06:00 tick queries `[10:05:00, 10:06:00]`. A session high printed at 10:04:30 falls in `[10:04:00, 10:05:00]`, which no evaluation ever reads. The alert stays silent about a level it was created to watch, and nothing anywhere records that a window was dropped.

A second, smaller version of the same issue: line 77 samples `Utc::now()` *after* evaluation, while each trigger's `context.now` was sampled at `alert_engine.rs:23` at the start of *its own* evaluation. The gap — evaluation duration, which includes blocking market-data round-trips — is excluded from both the window that just closed and the one that opens next.

**Fix.** Advance `last_eval_time` only on success, and set it to the `now` the evaluation actually used rather than a fresh sample. Sampling `now` once per `evaluate` call and threading it through removes the second issue at the same time.

---

### HIGH — Unknown `time_unit` silently shrinks the lookback window by up to 1440×
`src/alert/mod.rs:206-213` · fix: scoped · **latent** until `reduce_bars` is implemented

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

`time_unit` is a free-form client string — the proto types it as `string` with only *"e.g. \"MINUTE\""* as guidance (`alert.proto:94`) and no validation anywhere. The `_ => 60` arm turns every unlisted unit into a minute instead of rejecting it. The mismatch is visible inside a single generated expression: the window is computed with the defaulted unit while `time_unit` is passed through *verbatim* as the bar size (`mod.rs:127`, `:147`).

**Trace.** `BreakoutAbove{lookback_bars: 20, multiplier: 1, time_unit: "DAY"}` — a 20-day breakout, the most ordinary configuration this message exists for. `unit_seconds = 60` → duration `"1200s"` → the generated call is `reduce_bars('AAPL', 1, 'DAY', context.now - duration('1200s'), context.now, 'max', 'high')`: daily bars requested over a 20-*minute* window, wrong by 1440×. It will return at most one bar, so the trigger fires against effectively today's high and a "20-day breakout" alert fires on any intraday high. `"SECOND"`, `"WEEK"`, `"MIN"`, and `"Day"` (after `to_uppercase`, `"DAY"`) all take the same arm.

**Fix.** Return `Result` and reject unknown units, or make `time_unit` an enum in the proto. There's already a `TimeUnit` enum in `src/postgres/models.rs` used elsewhere in the repo — reusing it removes the free-string surface entirely.

---

### HIGH — `initial_state` is accepted over the wire and never read
`proto/poligun/ninniku/alert/alert.proto:53` · fix: scoped

The contract promises it works: *"Seed state for the very first evaluation, accessible as `context.state[\"key\"]`. On subsequent evaluations, `TriggerResult.next_state` takes precedence."* The only occurrence in Rust sets it to `None`.

```
$ rg -w 'initial_state' /Users/yuhanzhao/GitHub/ninniku/src /Users/yuhanzhao/GitHub/ninniku/proto
proto/poligun/ninniku/alert/alert.proto:53:  optional google.protobuf.Struct initial_state = 4;
src/alert/mod.rs:160:        initial_state: None,
```

`context.state` is populated exclusively from `evaluate_alert_definition`'s `states` vec (`alert_engine.rs:178,218-221`), which starts life as `vec![None; trigger_count]` (`alert_bot.rs:21`).

**Trace.** A user writes a `NativeTrigger` with `initial_state: {"hwm": 187.40}` and a binding `'hwm' in context.state ? context.state['hwm'] : price` — the exact pattern the built-in translator itself generates (`mod.rs:66-71`). On the first evaluation `context.state` is `{}`, so the guard takes the else branch and the watermark seeds from the current price instead of the user's 187.40. The alert silently arms at the wrong level and nothing reports a problem. The API accepted the field without complaint.

**Fix.** Seed `states[i]` from `trigger.initial_state` when it is `None` in `evaluate_alert_definition`, or reject `initial_state` at `CreateAlert` until it's supported. Accepting and ignoring is the one option that produces wrong alerts.

---

### MEDIUM — Five more declared surfaces have no consumer
`proto/poligun/ninniku/alert/alert.proto` · fix: scoped

Each grep below is the full hit list across `src/` and `proto/`.

| Declaration | Documented effect | Reality |
|---|---|---|
| `market_hours_filter` / `MarketHoursFilter` / `regular_hours` (`alert.proto:187,192-193`) | *"If absent, the alert always evaluates (suitable for 24/7 assets)"* — implying presence restricts | Proto-only, zero Rust hits. `AlertBot` reads `eval_schedule.interval` and nothing else (`alert_bot.rs:50-58`). Every alert evaluates 24/7, which multiplies the dedup finding overnight and on weekends. |
| `message_template` (`alert.proto:213`) | *"Binding names from the trigger are substituted as `{{name}}`. E.g. \"AAPL ask {{price}} crossed above {{threshold}}\""* | Read as a literal string at `alert_bot.rs:99`. `rg -i 'template\|substitut\|render' src/` returns that one line; `rg '\{\{' src/` returns only `format!` brace-escapes. A user's template arrives at the sink with `{{price}}` intact. |
| `Alert` message (`alert.proto:242-245`) | *"Full alert record stored in `AlertBotParams`"* | Never constructed or read in Rust. `AlertBotParams` holds an `AlertDefinition` directly (`server/mod.rs:614`), and `alert_id` is the bot_id echoed back. |
| `BotMetadata.can_trade` (`bot.proto:20`) | Persisted trading capability | Write-only. Written at `bot_manager.rs:147`; the one place that would read it deliberately re-derives instead — *"Re-derive `can_trade` from bot_config rather than trusting the stored field"* (`bot_manager.rs:116-117`). No reader in `src/` or `ninniku-fe`. |
| `Bar::get_highest_high` (`src/postgres/bar.rs:200`) | — | Zero callers. Notably it is the exact query `reduce_bars` needs, and `reduce_bars` returns `f64::NAN` instead (`alert_engine.rs:100-118`). |

`pre_market` / `post_market` are *not* on this list — the proto marks them "Not yet implemented" (`alert.proto:191,195`), which is disclosure rather than a defect.

**Fix.** Wire or delete. The `{{name}}` one is the most likely to reach a user as a visible defect, and the `get_highest_high` / `reduce_bars` pair looks like two halves of the same unfinished change that never met.

---

### MEDIUM — Unvalidated wire numbers panic or wrap before any guard sees them
`src/bot/alert_bot.rs:55-56` · fix: mechanical

`validate_alert_definition` checks that `eval_schedule.interval` is *present* and nothing else — not its sign, not its range (`src/server/mod.rs:692-696`). `d.seconds` is an `i64` straight off the wire:

```rust
                chrono::Duration::seconds(d.seconds)
                    + chrono::Duration::nanoseconds(d.nanos as i64)
```

chrono 0.4.45's `Duration::seconds` panics when the value is out of bounds. The same shape appears at `src/alert/mod.rs:212`, `lookback_bars * multiplier * unit_seconds` — three `i32`s, all client-supplied, all unvalidated.

**Trace.** *(a)* `CreateAlert` with `interval: {seconds: 9_223_372_036_854_775}` passes validation, then panics inside `AlertBot::evaluate` on the first tick. The loop runs under a bare `tokio::spawn` with no `catch_unwind` (`src/tasks.rs:36`), so the task dies; Redis still says `Running`; `background_tasks` is an append-only `Vec` never consulted by bot_id (`tasks.rs:18`). The alert is permanently dead and reports healthy. *(b)* `interval: {seconds: 0}` yields a zero duration, which `bot_loop.rs:40-48` rejects with an `error!` and a hard-coded 5 s retry — forever, one error log every 5 s. `NoopBot` guards this exact case with `max(1, params.interval_seconds)` (`src/bot/bot.rs:98`); `AlertBot` doesn't. *(c)* `BreakoutAbove{lookback_bars: 1000, multiplier: 1000, time_unit: "HOUR"}` → `1000 * 1000 * 3600` = 3.6e9, past `i32::MAX`. In debug that panics (same dead-task outcome); in release it wraps to `-694967296` and emits `duration('-694967296s')`. This one is *not* latent behind the `reduce_bars` stub — `lookback_duration` runs during translation, before any CEL executes.

**Fix.** Bound `interval` in `validate_alert_definition` (positive, and something like ≤ 24 h), and compute the lookback in `i64` with a checked multiply that returns `TranslationError`.

---

### MEDIUM — The one-trading-bot-per-account rule is enforced only at create
`src/bot/bot_manager.rs:154-180` · fix: scoped

`create_bot` re-derives `can_trade` and runs the uniqueness scan (`bot_manager.rs:113-137`). `update_bot_config` does neither — it rewrites the config and carries the rest of the metadata through unchanged:

```rust
        let new_metadata = BotMetadata {
            bot_config: Some(bot_config.clone()),
            ..metadata
        };
```

The comment on the invariant is at `bot.proto:18-19`: *"At most one trading bot may be registered per account; read-only bots (e.g. AlertBot) have no such limit."*

**Trace.** Account A already runs trading bot B1. `CreateAlert` on account A creates AlertBot B2 — correctly allowed, since `bot_can_trade` returns false for `AlertBotParams` (`bot_manager.rs:285-287`). The client then calls `UpdateBotConfig(B2, NoopBotParams)`; `server/mod.rs:567-586` does no type check, `update_bot_config` runs no uniqueness scan, and account A now has two order-capable bots. The stored `can_trade` on B2 stays `false` (`..metadata`), so the persisted record also disagrees with the config — harmless only because nothing reads the field (see the dead-surface table).

There is also a plain read-then-write race in `create_bot` itself: the scan reads at `:119` and the write lands at `:149` with no lock between, so two concurrent `create_bot` calls for one account both pass.

**Fix.** Recompute `can_trade` in `update_bot_config` and re-run the uniqueness check when it flips to `true`. Rejecting `UpdateBotConfig` for alert bots outright would close it too, and is arguably right anyway given `UpdateAlert` is unimplemented.

---

### LOW — Leftover debug log fires for every trigger on every tick
`src/bot/alert_bot.rs:90` · fix: mechanical · uncommitted

```rust
            info!("AlertBot: trigger {} fired — {}", i, result.fired);
```

This is the one uncommitted line in the branch (`git diff -- src/bot/alert_bot.rs`). It sits *above* the `if !result.fired { continue; }` guard, so it logs at `info` for triggers that did not fire, using the word "fired" for both outcomes. Line 106 then logs the same `"AlertBot: trigger {} fired"` prefix again for the ones that did.

**Trace.** An alert with 4 triggers at a 5 s interval emits 2,880 `info` lines an hour, of which the useful ones — those from line 106 — are indistinguishable by prefix from the noise.

**Fix.** Delete it, or move it below the guard and change the text so the two lines say different things.

---

## Questions I couldn't answer from the code

1. **Is a trigger meant to fire once on the crossing, or repeatedly while the condition holds?** This is the one that decides the shape of the CRITICAL fix. Edge-triggered costs a `fired` bit in `next_state` and no proto change; level-triggered-with-cooldown costs a new `EvalSchedule` field and persisted state that survives restarts. Everything downstream — whether restart re-notification is a bug or expected, whether `market_hours_filter` is a nice-to-have or load-bearing — follows from your answer.

2. **What was supposed to subscribe to `required_symbols`?** If the AlertBot is meant to register a subscription at start and drop it at delete, that's missing code and the alert feature does not work end-to-end today. If `latest_quote` is genuinely a fetch-on-demand call and no subscription is needed, then the proto comment at `alert.proto:233-235` is simply wrong and should be deleted — which would also make me downgrade that finding to LOW. I couldn't tell which from the code, because there is no subscription API on `MarketData` at all.

3. **Should `Decimal` be validated server-side, or is the "no validation" contract deliberate?** `well_known_types.proto:5-8` says the client is responsible for well-formed decimals. Taken at face value, `decimal() → 0.0` and the CEL interpolation are the contract working as written — which I don't believe, because the consequence is a silently inverted comparison. Either the contract line goes or the validation arrives; the current pairing is the worst of both.

4. **Is `UpdateBotConfig` supposed to be reachable for alert bots?** `UpdateAlert` is deliberately `unimplemented`, but `UpdateBotConfig` accepts `AlertBotParams` with no type check. If alert bots should reject it, the positional-state finding becomes latent rather than live and drops a severity band; if it's the intended update path until `UpdateAlert` lands, it needs the state-invalidation fix now.

5. **When `reduce_bars` is implemented, should a missing-data result be `NaN` or an error?** The stub picks `NaN` deliberately and the reasoning at `alert_engine.rs:114-115` is sound in isolation. But `latest_quote` picks the opposite convention for the same situation (`Ok(None) → Err`), and the batch-abort finding shows that convention has bad consequences. Two functions in one context disagreeing about what "no data" means will surprise expression authors.

6. **Is `f64` the intended arithmetic type for alert thresholds?** The comment at `src/alert/mod.rs:13-14` says state is stored as floats *"for direct CEL numeric comparison"*, so this reads deliberate — but `Decimal` exists in this repo specifically to represent prices *"without losing precision"*, and `to_f64().unwrap_or(0.0)` at `alert_engine.rs:55,59,85` converts away from `BigDecimal` at the boundary. For threshold comparison the error is almost certainly irrelevant; I'm asking because if it isn't, the fix is much cheaper now than after expressions exist in the wild. I did not file this as a finding.

---

## Proposed memory update

**Nothing was written.** No knowledge base exists at either location, and I'm not going to create one without your say-so:

```
$ ls /Users/yuhanzhao/GitHub/ninniku/.claude/
settings.local.json          # no knowledge/ subdirectory
$ ls ~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/
No such file or directory
```

The choice of location is also yours and is made once, by which directory gets created: **`<repo>/.claude/knowledge/`** means teammates and CI agents share it and it shows up in PR diffs; **`~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/`** means it never touches the repo but nobody else benefits. Below is the diff I'd apply, seeded only for the `alert` domain this review actually touched — I'm not backfilling the rest of the repo.

```diff
--- /dev/null
+++ b/.claude/knowledge/INDEX.md
@@
+---
+schema: knowledge/v1
+repo: ninniku
+updated: 2026-07-31
+---
+# Knowledge index
+
+Load this file always. Load a domain file when a changed path matches its globs. Load a
+findings ledger only before finalizing a finding in that domain.
+
+| path globs | domain | claims | last verified |
+|---|---|---|---|
+| `src/alert/**`, `src/bot/alert_bot.rs`, `proto/poligun/ninniku/alert/**` | `domains/alert.md` | 6 | 2026-07-31 @ b00b1d4 |
+
+Findings: `review/findings/alert.md` — 13 open, 0 fixed, 1 refuted
+
+## Repo-wide notes
+- Bot state (`trigger_states`, `last_eval_time`) is in-memory only; Redis stores
+  `BotMetadata` but never per-evaluation state. Any "survives restart" question is
+  answered "no" unless the answer is in Redis.
+- `BotStatus` has exactly two values, `Running` and `Stopped`. There is no error state, so
+  "does anyone find out about this failure?" is nearly always "only a log line."
```

```diff
--- /dev/null
+++ b/.claude/knowledge/domains/alert.md
@@
+---
+schema: knowledge/v1
+domain: alert
+paths: ["src/alert/**", "src/bot/alert_bot.rs", "proto/poligun/ninniku/alert/**"]
+updated: 2026-07-31
+head: b00b1d4
+---
+# Alert engine
+
+## Intent
+Evaluates user-defined price triggers on a schedule. `BuiltInTrigger` (structured) is
+translated to `NativeTrigger` (CEL source) at evaluation time, then compiled and executed
+against a context of `{now, last_eval_time, state, parameters}`. One `AlertBot` per alert.
+
+## Lifecycle maps
+
+### MAP-alert-001 — BuiltInTrigger is re-translated and re-compiled on every tick
+- kind: mechanism
+- provenance: code
+- status: active
+- anchor: src/alert/alert_engine.rs:156 `Some(TriggerType::BuiltInTrigger(built_in)) =>`
+- recorded: 2026-07-31 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'translate_built_in_trigger' src/alert/`
+- claim: `evaluate_trigger_config` clones the trigger and calls
+  `translate_built_in_trigger` on every evaluation; `Program::compile` then runs for each
+  binding plus the main expression. No caching. Any translation-time defect fires every
+  tick, and any malformed interpolation is a per-tick compile error, not a one-time one.
+- matters-because: makes translation-time panics (i32 overflow) and compile failures
+  recurring rather than create-time, which raises their severity.
+
+### MAP-alert-002 — Config update keeps the Bot instance and its state
+- kind: lifecycle
+- provenance: code
+- status: active
+- anchor: src/bot/bot_loop.rs:57 `context.update_bot_config(bot_config).await`
+- recorded: 2026-07-31 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'create_bot_from_config' src/`
+- claim: `BotEvent::ConfigUpdate` swaps only the `BotConfig` inside `BotContext`.
+  `create_bot_from_config` is never called again, so the same `Box<dyn Bot>` — and for
+  AlertBot the same positional `trigger_states` Vec and `last_eval_time` — survives an
+  arbitrary change to the trigger list. Only a full stop→start or a process restart
+  rebuilds it.
+- matters-because: turns every "can this collection be reordered?" question in the alert
+  domain from theoretical to live.
+
+## Invariants
+
+### INV-alert-003 — Per-trigger state is bound by list position, nothing else
+- kind: invariant
+- provenance: doc
+- status: active
+- anchor: src/bot/alert_bot.rs:12 `/// Per-trigger CEL state, indexed by trigger position`
+- recorded: 2026-07-31 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'trigger_states' src/bot/alert_bot.rs`
+- claim: there is no trigger identifier anywhere in `TriggerConfig` or `AlertDefinition`.
+  Position is the only correlation key between a trigger and its persisted CEL state.
+- matters-because: any A9 finding here is confirmed by construction, not inferred.
+
+## Taint sources
+
+### TAINT-alert-004 — Client strings are formatted directly into CEL source
+- kind: taint
+- provenance: code
+- status: active
+- anchor: src/alert/mod.rs:32 `let expr = format!("{{'fired': price >= decimal('{}')}}"`
+- recorded: 2026-07-31 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n "decimal\('\{\}'\)|latest_quote\('\{\}'\)" src/alert/mod.rs`
+- claim: `BuiltInTrigger.symbol` and every `Decimal.value` reach `Program::compile` by
+  string interpolation with no validation on the path. `Decimal`'s own contract
+  (proto/poligun/ninniku/well_known_types.proto:5-8) states the API performs no format
+  validation. Note the calibration: `NativeTrigger.expression` already accepts arbitrary
+  CEL from the same caller, so this is an integrity/availability issue, not privilege
+  escalation — don't re-report it as injection-to-RCE.
+- matters-because: sets the correct severity band for the next reviewer who finds it.
+
+## Absence claims
+
+### ABS-alert-005 — No dedup, cooldown, or edge detection anywhere in the tree
+- kind: absence
+- provenance: code
+- status: active
+- anchor: src/bot/alert_bot.rs:89 `for (i, result) in results.iter().enumerate()`
+- recorded: 2026-07-31 @ b00b1d4 (branch cel-alert)
+- verify: `rg -i 'cooldown|debounce|throttle|dedup|idempot|last_fired|last_sent|seen' src/ proto/`
+- claim: notification is level-triggered with no suppression of any kind. Re-run the verify
+  command every time; a negative grep is the weakest kind of entry.
+- matters-because: the single highest-impact finding in this domain rests entirely on it.
+
+## Open questions
+
+### Q-alert-006 — Is firing meant to be edge-triggered or level-triggered with a cooldown?
+- proposed answer (inferred, unconfirmed): edge-triggered — `RiseAbove` is documented as
+  "Fires when price rises above", and `TriggerResult.next_state` already exists as a place
+  to carry a `fired` bit across evaluations.
+- would change: the fix for the CRITICAL repeat-fire finding (a `next_state` bit vs. a new
+  `EvalSchedule.cooldown` field plus persisted `last_notified_at`), and whether
+  re-notification after a process restart is a bug.
+- asked: never
+
+### Q-alert-007 — What is supposed to subscribe to `required_symbols`?
+- proposed answer (inferred, unconfirmed): the AlertBot should subscribe at start and
+  unsubscribe at delete; the `MarketData` trait is missing the method to do it.
+- would change: severity of the `required_symbols` finding — HIGH if a subscription is
+  genuinely required for `latest_quote` to return data, LOW (a stale proto comment) if
+  `latest_quote` fetches on demand.
+- asked: never
```

```diff
--- /dev/null
+++ b/.claude/knowledge/review/findings/alert.md
@@
+# Alert — findings ledger
+
+## Open
+[13 FND entries corresponding to the findings above, each with severity, angle, anchor,
+trace, and fix clarity. Omitted from this preview for length — they are a mechanical
+transcription of the report's findings section.]
+
+## Fixed
+(none)
+
+## Won't fix
+(none)
+
+## Refuted (graveyard)
+
+### REF-alert-001 — "The reduce_bars NaN sentinel permanently poisons the trailing watermark"
+- reason_class: wrong-model
+- scope: this-site-only
+- re_raised: 1
+- refuted: 2026-07-31 @ b00b1d4
+- reasoning: Rust's `f64::max` returns the *other* operand when one side is NaN, so
+  `max_decimal(real_price, NaN)` yields `real_price`. A NaN watermark recovers on the first
+  evaluation that produces a real price rather than persisting. The correct model: NaN
+  *freezes* the watermark while it is present; it does not poison it.
+- guard_anchor: src/alert/alert_engine.rs:39 `ctx.add_function("max_decimal", |a: f64, b: f64| -> f64 { a.max(b) });`
+- void_if: `max_decimal` stops delegating to `f64::max`, OR trigger state starts being
+  serialized to JSON (protobuf JSON has no NaN representation for `google.protobuf.Value`).
```

Say the word and which location you want, and I'll write it. Declining is fine — it costs future reviews a lookup, nothing in this one.
