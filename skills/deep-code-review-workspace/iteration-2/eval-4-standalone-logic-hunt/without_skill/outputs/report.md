# Alert evaluation — logic review

I dug through `src/alert/alert_engine.rs`, `src/alert/mod.rs`, `src/bot/alert_bot.rs`, the `alert.proto` contract, and the `cel` 0.14 crate source to check the assumptions the code makes about CEL semantics.

Your instinct is right. There are four bugs I'd call correctness-critical, and the first one is the one I think you're feeling: **the NaN sentinel does the opposite of what the comment says.**

---

## Critical

### C1. The `reduce_bars` NaN sentinel aborts the whole alert instead of silently not firing

`src/alert/alert_engine.rs:113-116`:

```rust
// NaN is the safe sentinel: all IEEE 754 comparisons against NaN return false,
// so no trigger fires regardless of direction or baseline type.
f64::NAN
```

That reasoning holds for raw Rust `f64`. It does not hold for `cel` 0.14. In `cel-0.14.0/src/common/types/double.rs`:

```rust
impl Comparer for Double {
    fn compare(&self, rhs: &dyn Val) -> Result<Ordering, ExecutionError> {
        if let Some(rhs) = rhs.downcast_ref::<Self>() {
            Ok(self.0.partial_cmp(&rhs.0).ok_or(ExecutionError::NoSuchOverload)?)
```

`partial_cmp` returns `None` for NaN, so CEL turns it into `Err(NoSuchOverload)`, and every comparison operator (`objects.rs:1236-1282`) propagates it with `?`. So `price > bar_high` where `bar_high` is NaN does not evaluate to `false` — it raises an execution error.

The blast radius from there:

- `evaluate_native_trigger` returns `Err` (line 139)
- `evaluate_alert_definition` propagates it with `?` (line 180)
- `AlertBot` logs it and returns (`alert_bot.rs:82-84`)

**Every trigger in the definition is silently disabled, not just the breakout one.** And this isn't limited to `BreakoutAbove`/`BreakoutBelow` — the `High`, `Low`, and `Bar` baselines (`mod.rs:171-185`) also route through `reduce_bars`, so `price` itself becomes NaN and *any* trigger type built on those baselines dies too.

There's a second half to this. `max_decimal`/`min_decimal` (`alert_engine.rs:39-40`) use `f64::max`/`f64::min`, which **discard** NaN rather than propagating it:

```rust
f64::NAN.max(5.0) == 5.0   // not NaN
```

So for a `TrailingBelow` with a seeded `water_mark`, `new_hwm = max_decimal(NaN, 5.0)` silently becomes `5.0` — the sentinel vanishes from the watermark but is still present in `price`, and the comparison then errors anyway. The sentinel neither propagates consistently nor fails safely.

Third: if a NaN ever does reach `next_state`, `cel_value_to_prost_value` writes `NumberValue(f64::NAN)` into a `prost_types::Struct`. NaN is not representable in protobuf JSON, so anything that later serializes that state will fail.

If you want a real no-op sentinel here, the function needs to return `Err(ExecutionError)` and the caller needs to treat "this trigger couldn't evaluate" as a per-trigger skip (see C2), or `reduce_bars` needs to return a value that's genuinely inert for the comparison being performed — which differs by direction, so there isn't one.

### C2. One failing trigger kills all triggers, and already-applied state is kept

`src/alert/alert_engine.rs:177-187`:

```rust
for (i, trigger_config) in definition.triggers.iter().enumerate() {
    let state = states[i].as_ref();
    let result = evaluate_trigger_config(..)?;      // <-- aborts the loop
    if let Some(ref next) = result.next_state {
        states[i] = Some(next.clone());             // <-- but this already happened
    }
    results.push(result);
}
```

`states` is `&mut`, so mutations to earlier triggers persist. `results` is returned by value, so on the `?` path it's dropped. That gives you a genuinely bad interleaving:

1. Trigger 0 fires; its `hwm` advances and is written to `states[0]`.
2. Trigger 1 errors.
3. `AlertBot` logs the error at `alert_bot.rs:82` and discards *all* results.
4. Trigger 0's firing is never delivered — but its watermark has moved on, so it won't re-fire on that crossing.

For a trailing stop that's a permanently missed alert, not a delayed one.

This path is very easy to hit because `latest_quote` treats "no data" as an error (`alert_engine.rs:63-66`):

```rust
Ok(None) => Err(ExecutionError::function_error("latest_quote", format!("no data for symbol: {}", symbol))),
```

Combined with H1 below (nothing ever subscribes the symbols), a cold cache on one symbol takes down every trigger in the alert.

The loop should collect `Vec<Result<TriggerResult, _>>` and let each trigger fail independently.

### C3. `decimal()` returning 0.0 on parse failure turns a typo into an alert storm

`src/alert/alert_engine.rs:31-36`:

```rust
ctx.add_function("decimal", |s: Arc<String>| -> f64 {
    s.parse::<f64>().unwrap_or_else(|_| {
        warn!("decimal(): failed to parse '{}', returning 0.0", s);
        0.0
    })
});
```

`Decimal.value` is a free-form string, and `well_known_types.proto` says so explicitly: *"The API will not perform any validation on the format of the string."* `validate_alert_definition` (`src/server/mod.rs:682`) doesn't validate it either. So:

| Input | Generated expression | Behavior |
|---|---|---|
| `RiseAbove{price: "12.5O"}` (letter O) | `price >= 0.0` | **fires every interval, forever** |
| `RiseAbove{price: ""}` (field present, unset) | `price >= 0.0` | fires forever |
| `FallBelow{price: "abc"}` | `price <= 0.0` | never fires — silently dead alert |
| `TrailingBelow{percent_offset: "5%"}` | `new_hwm * (1.0 - 0.0)` | fires on any downtick |

A single mistyped character converts a threshold alert into an unbounded notification loop, and the only signal is a `warn!` line. This needs to be a hard validation error at `CreateAlert` time, and a parse failure at eval time should be an error rather than a value.

### C4. User-controlled strings are interpolated straight into CEL source

Every built-in translation `format!`s caller-supplied strings into CEL source with `'` as the delimiter — `mod.rs:32, 41, 52, 55, 61, 86, 90, 96, 127, 147`, and all of `translate_baseline` (`mod.rs:168-184`):

```rust
let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);
```

Neither `symbol` nor `Decimal.value` is validated anywhere. A symbol of:

```
AAPL') || true || latest_quote('AAPL
```

produces a syntactically valid expression whose `fired` value the caller fully controls. Less adversarially, any symbol or decimal containing an apostrophe or backslash produces a compile error, which per C2 takes down the entire alert definition.

The exposure is bounded (the CEL context only has the functions you registered, and `AlertBot` can't trade — `bot_manager.rs:286`), but a caller can force always-fire, always-error, or read quotes for arbitrary symbols. Either validate `symbol` against `^[A-Z0-9.\-/]{1,16}$` and `Decimal.value` as a parseable decimal at the server boundary, or pass these as `parameters` and reference them as `context.parameters['symbol']` instead of splicing them into source.

---

## High

### H1. `required_symbols` is never read

```
$ grep -rn "required_symbols" src/
(no matches)
```

`alert.proto:233-238` states: *"Symbols required across all triggers. The engine subscribes to market data for these symbols once for the whole alert."* Nothing subscribes. `latest_quote`/`latest_trades` return whatever some other bot happened to populate. For a symbol nobody else is watching, you get `Ok(None)` → error (C2) → the alert never works and only ever logs. I'd guess this is a large part of why it "feels off" in practice.

### H2. `NativeTrigger.initial_state` is never read

```
$ grep -rn "initial_state" src/
src/alert/mod.rs:160:        initial_state: None,
```

That's the only hit — a write, not a read. `evaluate_alert_definition` seeds `states[i] = None`, and `build_context_map` turns `None` into an empty map (`alert_engine.rs:218-220`). So a `NativeTrigger` that declares seed state gets `context.state == {}` on its first evaluation, and any expression doing `context.state['x']` without an `in` guard errors on cycle 1 — and, because state is only written from `next_state`, may never recover.

### H3. In-memory trigger state is lost on every restart

`AlertBot::new` (`alert_bot.rs:19-24`) initializes `trigger_states: Mutex::new(vec![None; trigger_count])`, and `create_bot_from_config` constructs a fresh `AlertBot` on every `start_bot`. `BotMetadata` in Redis stores `bot_config` only — no runtime state.

So every deploy, restart, or bot restart resets every trailing watermark. A `TrailingBelow` that has been tracking a high of $250 for a week silently re-seeds to the current price on the next deploy, and the stop it was protecting is gone. `last_eval_time` resets to `None` at the same time (see H4).

### H4. The `last_eval_time` window has a gap, and it advances even when evaluation fails

Three different clock reads are involved:

- `alert_bot.rs:67` — reads the stored `last_eval`
- `alert_engine.rs:23` — `let now = Utc::now();`, computed **per trigger**
- `alert_bot.rs:77` — `*self.last_eval_time.lock().await = Some(Utc::now());`, a third, strictly later instant

The stored value is later than the `now` that was used as the window end, so `[last_eval, now]` windows don't tile — bars landing in that gap fall into no window at all. The `High`/`Low`/`Bar` baselines (`mod.rs:171-185`) query exactly that range, so those bars are silently skipped.

Worse is the comment on line 76:

```rust
// Update last_eval_time regardless of evaluation outcome
```

If evaluation failed (market data blip, C1, C2), the window still advances, so the bars inside the failed window are dropped permanently. A session-high alert that should have fired during the failure never fires at all, and there's no record that it was skipped. On failure the timestamp should not advance.

Two smaller issues in the same area:

- Each trigger in a definition calls `Utc::now()` separately, so two triggers in one alert see different `context.now`. Hoist one `now` into `evaluate_alert_definition`.
- On the first evaluation, `last_eval_time` is `None` and gets defaulted to `now` (`alert_engine.rs:210-212`), producing a zero-width window. So the first cycle after every start returns nothing for those baselines, and user expressions computing `context.now - context.last_eval_time` see exactly `0` rather than being able to detect "never evaluated."

### H5. Positional trigger state misaligns when the config changes

`bot_loop.rs` handles `BotEvent::ConfigUpdate` and swaps the config live; `AlertBot::evaluate` re-reads `definition` on every cycle. But `trigger_states` is indexed by position and only ever **grows**:

```rust
// alert_bot.rs:63-65 and again in alert_engine.rs:171-173
while states.len() < trigger_count {
    states.push(None);
}
```

Remove or reorder a trigger and index `i` now refers to a different trigger while still holding the old one's `hwm`/`lwm` — an AAPL watermark gets applied to TSLA's price. Shrink the list then grow it again and the stale entries are silently reused.

The underlying gap is that `TriggerConfig` has no stable identifier to key state on. This needs a `trigger_id` in the proto and a `HashMap<String, Struct>` for state.

Note also that this growth loop is duplicated in both `alert_bot.rs` and `alert_engine.rs` — the `alert_bot.rs` copy is redundant.

### H6. Nothing latches a firing — alerts repeat every interval indefinitely

Once `price >= threshold`, `RiseAbove` returns `fired: true` on every single evaluation. There is no fired-state, no cooldown, no one-shot flag, and no edge detection (fire only on the `false → true` transition). At a 5-second interval that's 720 notifications per hour for one crossing, forever, until someone deletes the alert.

Neither the proto nor the engine has anywhere to put this. `TriggerResult` would need a `fired_at`/`latched` concept, or the built-in translations need to write `{'fired_already': true}` into `next_state` and guard on it.

---

## Medium

### M1. Breakout compares against a window that includes the current, in-progress bar

`alert.proto:149-150` specifies *"the highest high of the last lookback_bars **completed** bars."* The generated expression (`mod.rs:127`) passes `context.now` as the end:

```
reduce_bars('AAPL', 1, 'MINUTE', context.now - duration('300s'), context.now, 'max', 'high')
```

The in-progress bar is inside that window. If the baseline is a trade or quote contributing to that same bar, `price > bar_high` is unsatisfiable by construction — the price is already in the max. The end bound should be the last completed bar boundary.

The start bound has the same class of problem: `now - N*multiplier*unit` is not aligned to bar boundaries, so you get N or N+1 partial bars rather than exactly N. (The unused `Bar::get_highest_high` at `src/postgres/bar.rs:200` uses `start_time >= $6 AND start_time <= $7` — inclusive on both ends, so it will inherit the same off-by-one when it's wired up.)

### M2. `lookback_duration` has an overflow, a silent unit fallback, and no bounds

`src/alert/mod.rs:206-213`:

```rust
let unit_seconds: i32 = match time_unit.to_uppercase().as_str() {
    "MINUTE" => 60,
    "HOUR" => 3600,
    _ => 60,
};
format!("{}s", lookback_bars * multiplier * unit_seconds)
```

- **Overflow**: all three operands are `i32`. `lookback_bars=20000, multiplier=1, "HOUR"` overflows — panic in debug, wraparound (possibly negative) in release.
- **Zero**: `lookback_bars` defaults to `0` in proto3 and nothing validates it → `duration('0s')` → empty window.
- **Negative**: yields `duration('-600s')` → parse error → per C2, the whole alert dies.
- **Silent unit fallback**: `_ => 60` means `"DAY"` becomes 1 minute and `"SECOND"` becomes 60× too long. Both produce a plausible-looking but completely wrong lookback.
- **Inconsistency**: the fallback is applied only to the duration string. The raw `time_unit` is passed verbatim as the third argument to `reduce_bars`, so the aggregation granularity and the window length disagree about what the unit means.

### M3. `interval` is checked for presence but not for value

`validate_alert_definition` (`src/server/mod.rs:682`) only checks `.is_none()`. So:

- `{seconds: 0}` → `Duration::zero()` → `bot_loop.rs` rejects it as non-positive, logs an error, sleeps 5s, and loops forever without ever honoring the config.
- `{seconds: 0, nanos: 1}` → a 1ns wait → tight evaluation loop hammering Postgres and Alpaca as fast as the executor allows.
- Negative `seconds` → same as zero.

Validate a sane floor (and probably a ceiling) at the server boundary.

### M4. `MarketHoursFilter` is entirely unimplemented

```
$ grep -rn "market_hours\|MarketHours" src/
(no matches)
```

`EvalSchedule.market_hours_filter` is declared in the proto and read nowhere. Equity alerts evaluate 24/7.

### M5. No staleness check on quotes or trades

`latest_quote`/`latest_trades` return whatever is cached with no assertion about age — the handler at `alert_engine.rs:51-61` reads only `ask_price`/`bid_price` and drops the timestamp. Combined with M4, a `RiseAbove` on an equity can fire on Sunday afternoon against Friday's closing quote. Any price-based trigger needs a max-age guard.

### M6. `parse_trigger_result` silently coerces malformed results to "didn't fire"

`alert_engine.rs:274-294`:

```rust
let fired = map.map.get(&Key::String(Arc::new("fired".to_string())))
    .and_then(|v| if let Value::Bool(b) = v { Some(*b) } else { None })
    .unwrap_or(false);
```

Every failure mode collapses to the same silent outcome:

- `{'fired': 1}` (int, not bool) → `false`
- `{'fire': true}` (typo) → `false`
- `{'fired': cond ? true : null}` → `false`
- non-string `message` → dropped (lines 280-289)
- non-map `next_state` → dropped (lines 291-294)

There's no way to distinguish "the expression said no" from "the expression is malformed." Since expressions are user-authored and never validated at create time (see M9), that's the difference between a debuggable error and an alert that just quietly never works. These should be `Err`, not `unwrap_or(false)`.

### M7. Timestamps and durations in `next_state` are silently converted to null

`cel_value_to_prost_value` (`alert_engine.rs:317-337`) has a catch-all:

```rust
_ => Kind::NullValue(0),
```

which swallows `Value::Timestamp`, `Value::Duration`, and `Value::Bytes`. The most natural way for a user to implement a cooldown is:

```
next_state: {'last_fired': context.now}
```

That round-trips to `null`, and the next evaluation's guard silently misbehaves. Since `prost_types::Value` has no timestamp variant, this at minimum needs to serialize to an RFC-3339 string — and it should never be a silent fallthrough.

Related precision issue: `Value::Int(i) => Kind::NumberValue(*i as f64)` loses precision above 2^53, and every number round-trips back as `Value::Float` (`prost_value_to_cel:253`), so integer state silently becomes floating point across evaluations. Any expression using `%` on it will fail with `NoSuchOverload`.

### M8. Sink template substitution is specified but not implementable as designed

`alert.proto:210-212` documents *"Binding names from the trigger are substituted as {{name}}. E.g. 'AAPL ask {{price}} crossed above {{threshold}}'"*. `alert_bot.rs:95-103` uses `message_template` verbatim with no substitution.

The deeper problem is that this can't be implemented without a protocol change: `TriggerResult` has no field carrying binding values, and `evaluate_native_trigger` drops the entire CEL context when it returns. The bindings the template needs no longer exist by the time `AlertBot` builds the message.

### M9. CEL is recompiled every cycle, and invalid expressions aren't caught until runtime

`Program::compile` runs on every binding and on the main expression on every evaluation (`alert_engine.rs:122, 135`), and for `BuiltInTrigger`s the CEL source is re-`format!`ed from scratch each time too (`alert_engine.rs:157`). At a 5s interval that's a full parse per binding per trigger per tick.

The correctness consequence matters more than the cost: a syntactically invalid `NativeTrigger` expression is accepted by `CreateAlert`, the bot starts successfully, and it then fails on every evaluation forever. Compile once at create time (as validation) and cache the compiled `Program`.

### M10. The `High`/`Low` baselines aren't session highs

`alert.proto:87-88` describes these as *"session high via reduce_bars"* / *"session low"*. The implementation (`mod.rs:171-178`) windows them to `[context.last_eval_time, context.now]` — the high **since the last evaluation**, which at a 30s interval is roughly a 30s high. Combined with H4 (the window advances on failure) and the zero-width first window, this is not a session extreme by any reading.

---

## Low

- **L1** — `alert_bot.rs:90` (your uncommitted line) logs `"AlertBot: trigger {} fired — {}"` for triggers that did **not** fire, before the `continue`. Any log scrape or alert on that string will match non-events, and line 106 then logs the same prefix again for real firings.
- **L2** — Binding names are inserted into the context with no reserved-word check (`alert_engine.rs:131`). A binding named `context` shadows the entire context map for every subsequent binding and the main expression. Duplicate binding names silently overwrite each other.
- **L3** — `Context::add_variable_from_value` does `value.try_into().unwrap()` internally (`cel-0.14.0/src/context.rs:82`), and the `TryFrom<Value> for Box<dyn Val>` impl has an `Err` arm (`objects.rs:987`). A binding evaluating to an unsupported variant would panic rather than error, killing the bot task. Not reachable with your current function set, but it's an unwrap on user-controlled input.
- **L4** — `tokio::task::block_in_place` (`alert_engine.rs:47, 77`) panics on a current-thread runtime. Production is fine (`main.rs:37` is `multi_thread`), but it means the engine can't be exercised from a plain `#[tokio::test]`, which may be why there are none.
- **L5** — There are **zero tests** in `src/alert/`. `translate_built_in_trigger`, `lookback_duration`, `parse_trigger_result`, and the four prost↔CEL converters are all pure functions and cheap to cover. `lookback_duration` alone would have caught M2.
- **L6** — `update_alert` returns `unimplemented` while `create_alert` starts the bot, so the only way to change an alert is delete + recreate — which destroys all trailing watermark state (H3).
- **L7** — The proto's own `NativeTrigger` example (`alert.proto:41-45`) doesn't work against this implementation. It uses `TriggerResult{ fired: ..., next_state: {...} }` message-construction syntax, but `parse_trigger_result` requires a plain `Value::Map`. It also stores the watermark as `string(new_hwm)`, which `max_decimal(a: f64, b: f64)` rejects — cel's `f64` extraction is strict (`magic.rs:11`, `Value::Float` only). `mod.rs:14` says the opposite in a comment ("stored as floats (not strings)"). Anyone following the documented example gets a runtime type error.

---

## Suggested order

1. **C1** — replace the NaN sentinel; it's actively breaking every alert that touches `reduce_bars`, including all `High`/`Low`/`Bar` baselines.
2. **C2** — make per-trigger evaluation independent, and stop persisting state for results you're about to discard.
3. **C3 / C4** — validate `Decimal.value` and `symbol` in `validate_alert_definition`; both are one-line fixes with outsized impact.
4. **H1 / H2** — wire up `required_symbols` and `initial_state`, or delete them from the proto so they stop reading as implemented.
5. **H5** — add a `trigger_id` to `TriggerConfig` and key state by id before someone edits a live alert.
6. **H3 / H6** — these are design decisions rather than bugs: persist state across restarts, and decide what "fired" means for repeat delivery.

The single highest-leverage change is C1 — until `reduce_bars` stops poisoning the entire evaluation, several of the others are masked behind it.
