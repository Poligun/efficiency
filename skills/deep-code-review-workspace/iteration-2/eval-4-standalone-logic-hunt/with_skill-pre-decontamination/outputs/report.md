## Review: `cel-alert` — CEL-evaluated price alerts as a new bot type

Your instinct is right, and I think what's bothering you is that the *shape* of the code is
defensive everywhere — `unwrap_or`, NaN sentinels, `warn!` on every failure path — while the
behavior underneath is "keep going and produce a wrong answer." Almost every finding below is
a place where a failure turns into a value instead of an error. Two things stand out as
ship-blockers: **`DeleteAlert` can never succeed on an alert created by `CreateAlert`**, and
**a malformed price string makes `RiseAbove` fire unconditionally on every evaluation**.

Read the whole thing with one caveat in mind: the Telegram sink is a `TODO`, so today every
"the alert notifies" consequence below terminates in an `info!` line. These are all latent
until `alert_bot.rs:105` is wired up — which is exactly when they become expensive.

**Angles run.** A1 lifecycle, A2 repeat-fire, A3 boundary/window, A4 fallback/sentinel,
A5 partial failure, A6 declared surface (all six core). Conditionals: A7 taint fired
(`format!` builds CEL), A8 numeric domain fired (arithmetic on request-supplied ints, float
money), A9 identity fired (`states[i]` is positional). A10 concurrency fired on the gate
(`block_in_place`, `Mutex`, broadcast channel) but produced nothing I could pin a second
concurrent actor to, so I'm reporting none of it rather than speculating. A6 and A7 ran as
subagents (repo-wide grep fan-out and a dig into the vendored `cel` crate); the rest ran
inline so one reader held the whole model. No knowledge base exists at
`.claude/knowledge/` or `~/.claude/projects/…/knowledge/`, so this review ran with zero
priors — every question in the last section is genuinely open.

**What I cut** to stay near the finding cap, all lower-severity: the `Alert` proto message is
declared and never used (and its doc comment says it's "stored in AlertBotParams", which
stores an `AlertDefinition` instead); `BackgroundTaskManager.background_tasks` never removes
finished handles; `create_bot`'s one-trading-bot-per-account check is a read-then-write with
no lock; and the uncommitted `info!("AlertBot: trigger {} fired — {}")` at `alert_bot.rs:90`
logs `fired — false` for every non-firing trigger on every cycle.

---

## Needs a decision before merge

### F1 — Nothing makes a firing happen at most once (HIGH · needs a decision)
`src/bot/alert_bot.rs:89` · `src/alert/mod.rs:32`

`evaluate` notifies for every trigger whose `fired` is true, on every cycle, and there is no
edge detection, cooldown, dedup key, or "already notified" marker anywhere in the branch.
`RiseAbove` and `FallBelow` don't even emit a `next_state`, so a user can't build one
themselves — the only key they could persist through isn't written.

```rust
// src/bot/alert_bot.rs:89-93
for (i, result) in results.iter().enumerate() {
    if !result.fired {
        continue;
    }
```
```rust
// src/alert/mod.rs:32 — note: no 'next_state' key at all
let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);
```

Negative grep establishing absence:
`rg -n 'cooldown|debounce|throttle|dedup|idempot|already_fired|last_fired|last_sent|edge' src/`
→ 2 hits, both the substring "edge" inside the word "Acknowledges" in
`bot_manager.rs:30,32`. No real mechanism exists.

**Trace.** `RiseAbove{price: "150.00"}` on AAPL with `eval_schedule.interval = {seconds: 5}`.
AAPL opens at 151 and stays there. The trigger returns `fired: true` on every cycle:
**720 notifications per hour, 5,760 per trading day, until the user deletes the alert** — and
per F2 they currently can't delete it. At the documented default of 30s it's still 120/hour.

**Fix.** This is a product call, so I'm not guessing. The proto's own wording is edge-flavored
("Fires when price **rises above**…", "Fires when price **falls below**…", `alert.proto:117-163`),
which is what makes me raise it — but the `AlertDefinition` contract at `alert.proto:223-225`
only says "The alert fires when any trigger returns `TriggerResult{fired: true}`", which is
level-neutral. **If level-triggered is intended, this drops to a MEDIUM documentation gap and
the fix is to say so in `alert.proto`.** If edge-triggered is intended, the fix is a
persisted `last_fired` per trigger index, or a `RiseAbove`/`FallBelow` translation that emits
`next_state: {'was_above': ...}` and gates on the transition. See Q1.

---

## Findings

### F2 — `DeleteAlert` can never succeed on an alert `CreateAlert` made (CRITICAL · scoped)
`src/server/mod.rs:658` · `src/bot/bot_manager.rs:191`

`create_alert` calls `create_bot` and then `start_bot`, so every alert reaches
`BotStatus::Running`. `delete_bot` refuses to delete a bot in that state, and the alert API
surface has no stop operation — `ninniku.proto` adds only Create/Update/Delete. Follow the
call sequence rather than each function alone and the delete path is unreachable by
construction.

```rust
// src/bot/bot_manager.rs:191-193
if metadata.status == BotStatus::Running as i32 {
    return Err(format!("Cannot delete a running bot: {}", bot_id).into());
}
```
```proto
// proto/poligun/ninniku/ninniku.proto:60-61 — the contract says otherwise
// Each alert runs in its own AlertBot. CreateAlert creates (and starts) the
// AlertBot; DeleteAlert stops and removes it unconditionally.
```

**Trace.** `CreateAlert` → `create_bot` writes metadata with `status: Stopped`
(`bot_manager.rs:143`) → `start_bot` → `resume_bot` spawns the loop → the loop sends
`BotAckEvent::Started` (`bot_loop.rs:15`) → `bot_manager_loop` flips Redis to `Running`
(`bot_manager.rs:356`). Now `DeleteAlert(alert_id)` → ownership check passes →
`delete_bot` → `Status::internal("Cannot delete a running bot: <uuid>")`. **100% of alerts,
100% of the time.** The only escape is `UpdateBotStatus(bot_id, STOPPED)` — a *bot* RPC, and
even that is racy: `stop_bot` only sends an event and returns `Ok` immediately, so a
`DeleteAlert` issued right after still sees `Running` until the async ack lands.

**Fix.** Either have `delete_alert` stop-and-wait before calling `delete_bot`, or give
`delete_bot` a force path for read-only bots. Related: `delete_alert` also doesn't check that
the target is an `AlertBot` at all — see F14.

---

### F3 — A malformed price string makes the alert fire unconditionally (CRITICAL · scoped)
`src/alert/alert_engine.rs:32`

`decimal()` is the only bridge from the user's `Decimal.value` string into the comparison, and
on a parse failure it substitutes `0.0` and logs a warning. Trace that value into the decision
it feeds and it doesn't degrade the comparison — it inverts it.

```rust
// src/alert/alert_engine.rs:31-36
ctx.add_function("decimal", |s: Arc<String>| -> f64 {
    s.parse::<f64>().unwrap_or_else(|_| {
        warn!("decimal(): failed to parse '{}', returning 0.0", s);
        0.0
    })
});
```

This is reachable by design, not by abuse — `well_known_types.proto:5-9` states outright:
*"The API will not perform any validation on the format of the string, so it is the
responsibility of the client to ensure that it is a valid decimal number."* And
`validate_alert_definition` (`src/server/mod.rs:682-701`) checks only that `triggers` is
non-empty, `interval` is present, and `sink` is present — it never looks at a `Decimal`.

**Trace.** A UI sends `RiseAbove{price: Decimal{value: "1,000.00"}}` — a thousands separator,
the single most common way a formatted price reaches an API. `CreateAlert` returns
`Ok(alert_id)`. At eval time the expression is `{'fired': price >= decimal('1,000.00')}`;
`"1,000.00".parse::<f64>()` fails; the comparison becomes `price >= 0.0`, **true for every
positive price**. Combined with F1, the user gets a notification every 5 seconds forever for
a stock that never came near $1,000. `"$100"`, `""`, and `"100.00 USD"` all do the same.

And the inverse is in the same file: the identical input on `FallBelow` (`mod.rs:41`) produces
`price <= 0.0`, which is **never** true — that alert is silently dead and the user is never
told. One fallback that makes a condition always true and one that makes it always false, both
from the same helper.

**Fix.** `decimal()` should return `Result<f64, ExecutionError>` like `latest_quote` already
does, so a bad parse fails the evaluation loudly instead of answering. Better still, reject
unparseable decimals in `validate_alert_definition` so `CreateAlert` fails synchronously —
the client can act on a `400`, but nobody reads the `warn!`.

---

### F4 — The NaN sentinel silently kills three baselines, not just breakouts (HIGH · scoped)
`src/alert/alert_engine.rs:98` · `src/alert/mod.rs:171`

The stub's comment scopes its own blast radius to breakout triggers. But `reduce_bars` is also
how `translate_baseline` resolves the `high`, `low`, and `bar` baselines — so NaN becomes the
`price` binding for *any* trigger type built on those baselines.

```rust
// src/alert/alert_engine.rs:98-99, 114-116
// --- reduce_bars: stub — bar range queries not yet in MarketData trait.
//     Returns sentinel values so breakout triggers silently never fire.
// NaN is the safe sentinel: all IEEE 754 comparisons against NaN return false,
// so no trigger fires regardless of direction or baseline type.
f64::NAN
```
```rust
// src/alert/mod.rs:171-174 — a non-breakout trigger routed through the same stub
Some(BaselineType::High(())) => format!(
    "reduce_bars('{}', 1, 'MINUTE', context.last_eval_time, context.now, 'max', 'high')",
    symbol
),
```

**Trace.** `RiseAbove{price: "150.00"}` with `baseline: {bar: {multiplier: 5, time_unit:
"MINUTE", field: close}}` — a completely reasonable "alert me when the 5-minute close crosses
150." `price` binds to NaN; `NaN >= 150.0` is false; the alert never fires, forever, and the
only signal is one `warn!` line per trigger per cycle. **Four of six `BuiltInTrigger` types
and three of six baseline types are silently non-functional**, while `CreateAlert` accepts
them all with a success response.

Also note `src/postgres/bar.rs:200` adds `get_highest_high` — a bar range query — in this very
branch, and `rg -n 'get_highest_high' src/` returns exactly one hit: the definition. The
replacement for the stub was written and never connected.

**Fix.** Either reject `high`/`low`/`bar` baselines and breakout triggers in
`validate_alert_definition` with `Status::unimplemented` (honest, and fails at create time),
or wire `reduce_bars` to `Bar::get_highest_high` and its siblings. At minimum, correct the
comment — its claim about "regardless of baseline type" is what makes the stub look safe.

---

### F5 — An unrecognized `time_unit` silently becomes minutes (HIGH · mechanical)
`src/alert/mod.rs:206`

The unit lookup has a default arm, and the default is not "error" — it's "60."

```rust
// src/alert/mod.rs:206-213
fn lookback_duration(lookback_bars: i32, multiplier: i32, time_unit: &str) -> String {
    let unit_seconds: i32 = match time_unit.to_uppercase().as_str() {
        "MINUTE" => 60,
        "HOUR" => 3600,
        _ => 60,
    };
    format!("{}s", lookback_bars * multiplier * unit_seconds)
}
```

`time_unit` is a free-form `string` (`alert.proto:153`, comment `// e.g. "MINUTE"`) with no
enum and no validation.

**Trace.** `BreakoutAbove{lookback_bars: 20, multiplier: 1, time_unit: "DAY"}` — "break out of
the 20-day range." `"DAY"` hits `_ => 60`, so the lookback becomes `1200s` = **20 minutes
instead of 20 days: wrong by a factor of 1,440**, with no warning. `"SECOND"` is wrong by 60×
in the other direction. Once `reduce_bars` is real, this is a wrong answer that looks
completely plausible in the logs.

**Fix.** Return `Err` on the default arm — `lookback_duration`'s callers are already in a
`Result` context (`translate_built_in_trigger` returns `Result<_, TranslationError>`), so this
is a two-line change. Longer term, `time_unit` should be the `TimeUnit` enum the repo already
has in `postgres::models`, not a string.

---

### F6 — Request-supplied numbers can panic the bot task, permanently (HIGH · scoped)
`src/alert/mod.rs:212` · `src/bot/alert_bot.rs:55`

Two arithmetic sites operate directly on ints from the gRPC request with no bounds check, and
both can panic. A panicking background task is logged only at shutdown and never restarted.

```rust
// src/alert/mod.rs:212 — i32 * i32 * i32
format!("{}s", lookback_bars * multiplier * unit_seconds)
```
```rust
// src/bot/alert_bot.rs:55-56 — chrono's Duration::seconds panics out of range
chrono::Duration::seconds(d.seconds)
    + chrono::Duration::nanoseconds(d.nanos as i64)
```

`~/.cargo/registry/…/chrono-0.4.45/src/time_delta.rs:208-215` documents:
*"Panics when `seconds` is more than `i64::MAX / 1_000`…"*. And `src/tasks.rs:36,49` shows a
spawned task's panic is surfaced only by `cancel_and_wait_for_all_join_handles` at process
shutdown — nothing restarts it.

**Trace.** `CreateAlert` with `eval_schedule.interval = {seconds: 9223372036854776}` passes
`validate_alert_definition` (it only checks presence). On the first `evaluate`, `Duration::seconds`
panics; the spawned task unwinds and dies. Redis still says `Running`, so `resume_bots` won't
restart it on the next server boot and `DeleteAlert` refuses it forever (F2) — **one valid RPC
produces a permanently dead, permanently undeletable alert**. Separately,
`BreakoutAbove{lookback_bars: 1000000, multiplier: 1000, time_unit: "HOUR"}` computes
`1000000 * 1000 * 3600` = 3.6e12 in `i32`: panic in a debug build, silent wraparound to a
negative duration string like `"-1471228928s"` in release.

Related and lower-cost: `validate_alert_definition` accepts `interval = {nanos: 1}`, which
passes `bot_loop.rs:40`'s `duration <= zero` check and gives you a near-tight evaluation loop
hammering the market-data API.

**Fix.** Validate the interval range at `src/server/mod.rs:692` (a sane floor of ~1s and a
ceiling), use `checked_mul` / `TimeDelta::try_seconds` at both sites, and validate
`lookback_bars`/`multiplier` as positive and bounded.

---

### F7 — One trigger's error abandons the rest, after mutating their state (HIGH · scoped)
`src/alert/alert_engine.rs:180`

The `?` inside the loop makes a batch of independent items behave like a transaction — except
it isn't one, because `states` has already been mutated in place for the triggers that ran
before the failure. The results of those triggers are discarded.

```rust
// src/alert/alert_engine.rs:177-187
for (i, trigger_config) in definition.triggers.iter().enumerate() {
    let state = states[i].as_ref();
    let result =
        evaluate_trigger_config(trigger_config, state, last_eval_time, market_data.clone())?;

    if let Some(ref next) = result.next_state {
        states[i] = Some(next.clone());
    }
```

The contract says these are independent: *"One or more triggers evaluated on each tick. The
alert fires when **any** trigger returns `TriggerResult{fired: true}`. **Each trigger maintains
independent state** across evaluations."* (`alert.proto:223-226`).

**Trace.** An alert with `[TrailingBelow(AAPL), RiseAbove(TSLA)]`. AAPL's trigger evaluates,
fires, and writes `states[0] = {hwm: 250.0}`. TSLA's trigger calls `latest_trade("TSLA")`,
which returns `Ok(None)` because no trade has arrived yet — and `alert_engine.rs:89-92` turns
`Ok(None)` into an `ExecutionError`. The `?` at line 180 discards the entire `results` vec,
`alert_bot.rs:81-84` logs and returns, and **AAPL's firing is thrown away while its water mark
has already advanced**. With one illiquid symbol in the list, every trigger positioned after
it never notifies, on every cycle, indefinitely. The user's only signal is an `error!` line.

**Fix.** Collect per-trigger `Result`s instead of propagating: push an error marker into
`results`, keep evaluating, and surface per-trigger failure somewhere a human sees it. Note
"no data yet for this symbol" probably shouldn't be an error at all — see Q3.

---

### F8 — Trailing water marks are lost on every restart (HIGH · scoped)
`src/bot/alert_bot.rs:13` · `src/alert/mod.rs:68`

`TriggerResult.next_state` is documented as *"State to **persist** and pass to the next
evaluation"* (`alert.proto:20-21`). It is persisted only in process memory.

```rust
// src/bot/alert_bot.rs:13
trigger_states: Mutex<Vec<Option<prost_types::Struct>>>,
```

`rg -n 'trigger_states|next_state' src/` returns 10 hits, all in `alert_bot.rs` and
`alert/`; there is no Redis or Postgres write on that path. `BotMetadata` *is* persisted
(`bot_metadata.rs`, base64 protobuf in Redis) and carries the `AlertDefinition`, but not the
evaluated state. `resume_bots` reconstructs the bot via `create_bot_from_config` →
`AlertBot::new(trigger_count)` → `vec![None; trigger_count]` (`alert_bot.rs:21`).

**Trace.** A `TrailingBelow{price_offset: "5.00"}` on a stock that ran from 100 to 250 over a
week has `state = {hwm: 250.0}` and is armed to fire at 245. The server is redeployed while
the stock sits at 251. On restart the state is empty, so the CEL fallback
`'hwm' in context.state ? context.state['hwm'] : price` (`mod.rs:68`) **re-seeds the high water
mark from the current price** — 251 becomes the new peak, the trigger now fires at 246, and a
week of tracked high is gone. The user is never told; a trailing stop that silently resets is
worse than one that errors.

**Fix.** Write `trigger_states` back into `BotMetadata` (or a sibling Redis key) after each
cycle, keyed so it survives `resume_bots`. If in-memory-only is a deliberate v1 choice, the
proto comment needs to stop saying "persist" — see Q4.

---

### F9 — Positional trigger state survives a config change (HIGH · scoped)
`src/alert/alert_engine.rs:171` · `src/bot/alert_bot.rs:63`

State is correlated to triggers by list index, and the vector only ever grows. A config update
replaces the trigger list while the state vector persists, silently rebinding one trigger's
history to a different trigger.

```rust
// src/alert/alert_engine.rs:171-173 — grows, never shrinks, never clears
while states.len() < definition.triggers.len() {
    states.push(None);
}
```

The update path is live: `UpdateBotConfig` → `BotEvent::ConfigUpdate` →
`bot_loop.rs:56` → `context.update_bot_config(bot_config)`. That swaps the config inside
`BotContext` but does **not** recreate the `Box<dyn Bot>` — `create_bot_from_config` is only
called from `resume_bot` (`bot_manager.rs:241`). So the `AlertBot` instance, and its
`trigger_states`, outlive the definition they were built for. (`UpdateAlert` itself returns
`unimplemented`, so `UpdateBotConfig` on the alert's bot_id is the reachable path today.)

**Trace.** An alert with `[TrailingAbove(AAPL), TrailingAbove(TSLA)]` accumulates
`states = [{lwm: 180.0}, {lwm: 390.0}]`. The user removes the AAPL trigger, leaving
`triggers = [TrailingAbove(TSLA)]`. `states` still has length 2 and is never truncated, so
TSLA now reads `states[0] = {lwm: 180.0}`. `new_lwm = min_decimal(390.0, 180.0)` = **180**, and
with a `price_offset` of `5.00` the trigger's threshold becomes `185` — **TSLA at 390 fires
immediately and keeps firing**, because AAPL's low water mark is now TSLA's.

**Fix.** Key the state by trigger identity rather than position, or clear `trigger_states` when
the definition changes. The `AlertDefinition` has no per-trigger id today, so adding one is
probably the cleaner half of the fix.

---

### F10 — `NativeTrigger.initial_state` is declared and never read (HIGH · mechanical)
`proto/poligun/ninniku/alert/alert.proto:53` · `src/alert/alert_engine.rs:27`

```proto
// alert.proto:51-53
// Seed state for the very first evaluation, accessible as context.state["key"].
// On subsequent evaluations, TriggerResult.next_state takes precedence.
optional google.protobuf.Struct initial_state = 4;
```

`rg -n 'initial_state' src/` returns exactly one hit: `src/alert/mod.rs:160`, the line
`initial_state: None` in a struct literal. `evaluate_native_trigger` takes `state` as a
parameter and never touches `trigger.initial_state`:

```rust
// src/alert/alert_engine.rs:27
let context_val = build_context_map(now, last_eval_time, state, &trigger.parameters);
```

And the first evaluation's `state` is unconditionally `None` — `vec![None; trigger_count]` at
`alert_bot.rs:21`, topped up with `None` at `alert_bot.rs:63` and `alert_engine.rs:171`.

**Trace.** A user writes a `NativeTrigger` implementing a trailing stop, sets
`initial_state = {'hwm': 250.0}` to seed it from a position they already hold, and writes
`prev_hwm = 'hwm' in context.state ? context.state['hwm'] : 0.0`. On the first evaluation
`context.state` is `{}`, so `prev_hwm` is `0.0`, and `price <= 0.0 - offset` is never true —
**the alert is dead on arrival and the field they set had no effect whatsoever.** This is the
one place where a caller sets a value, is told it will do something, and gets silence.

**Fix.** In `build_context_map`, fall back to `trigger.initial_state` when `state` is `None`.
That's a one-line change and it makes the documented "on subsequent evaluations, `next_state`
takes precedence" true.

---

### F11 — Unvalidated strings are interpolated into the CEL source (HIGH · scoped)
`src/alert/mod.rs:32` · `src/alert/mod.rs:168`

Every `BuiltInTrigger` is compiled by building CEL *source text* with `format!`, and three
request-controlled strings — `Decimal.value`, `symbol`, and `time_unit` — go in raw. A single
quote in any of them changes the structure of the expression, not just a value in it.

```rust
// src/alert/mod.rs:32
let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);
// src/alert/mod.rs:168
Some(BaselineType::Ask(())) => format!("latest_quote('{}').ask", symbol),
```

`grep -rnE 'escape|sanitize|is_alphanumeric|is_ascii|replace\(' src/` → **zero matches**. The
CEL grammar does support the escape (`cel-0.14.0/src/parser/gen/CEL.g4:193-202`; `\'` inside a
single-quoted literal, with a passing test at `parse.rs:417`) — the host just never applies it.

**Trace.** `RiseAbove.price.value` set to
`0'), 'fired': true, 'next_state': {'hwm': 0.0}, 'x': decimal('0`
produces the expression
`{'fired': price >= decimal('0'), 'fired': true, 'next_state': {'hwm': 0.0}, 'x': decimal('0')}`.
The one-key map becomes a four-key map; `parse_trigger_result` (`alert_engine.rs:274-294`)
reads `fired` and `next_state` straight out of it, so the price comparison is bypassed
entirely and attacker-chosen state is written into `trigger_states`. A less exotic version of
the same bug: a symbol or decimal containing a stray `'` produces a CEL *compile* error, which
`CreateAlert` doesn't catch (translation happens at eval time, `alert_engine.rs:156-158`), so
the RPC returns success and the alert logs a compile failure every cycle forever.

**Honest scoping, because it changes the severity.** This is **not** privilege escalation.
`TriggerConfig` already offers `native_trigger`, whose `expression` and every `binding.expression`
are compiled with zero validation (`alert_engine.rs:121-139`) — anyone who can inject through
`Decimal.value` can already submit arbitrary CEL through the front door. The CEL sandbox has
no file, network, or process primitives; the worst reachable side effect is calling
`latest_quote`/`latest_trade` many times per cycle (each is a blocking `block_in_place`), which
is a CPU/thread-pool concern rather than a data-exfiltration one. So I'm rating this as a
correctness and defense-in-depth failure, not a breach.

**Fix.** Escape both quote characters at every interpolation site (the `cel` crate supports
`\'`), or better, validate `Decimal.value` by parsing it and re-emitting a canonical numeric
literal, and constrain `symbol` to an allowlist character class. Given that `NativeTrigger`
is the real trust boundary here, Q6 is the question that actually matters.

---

### F12 — Four declared surfaces have no consumer (MEDIUM · scoped)
`proto/poligun/ninniku/alert/alert.proto:238, 187, 212` · `src/postgres/bar.rs:200`

Each of these is documented as having an effect, is settable by a caller, and does nothing.
Grep results are from a repo-wide sweep excluding generated code under `target/`.

| Declaration | Documented effect | Consumers in `src/` |
|---|---|---|
| `AlertDefinition.required_symbols` (`:238`) | "The engine subscribes to market data for these symbols once for the whole alert" | **none** — `rg -n 'subscribe\|Subscription' src/alert/ src/bot/alert_bot.rs` → 0 hits. Data is pulled per-evaluation inside CEL instead. |
| `EvalSchedule.market_hours_filter` / `MarketHoursFilter.regular_hours` (`:187,:194`) | controls which sessions are active for evaluation | **none** — `rg -n 'market_hours\|regular_hours\|is_market_open\|session' src/` → 0 hits. Only `eval_schedule.interval` is ever read. |
| `Sink.TelegramNotification.message_template` (`:213`) | "Binding names from the trigger are substituted as `{{name}}`" | read as a raw fallback string at `alert_bot.rs:99`; **no substitution exists** — `rg -n '\{\{' src/` → 6 hits, all Rust `format!` brace escapes. |
| `Bar::get_highest_high` (`bar.rs:200`) | added in this branch | **none** — `rg -n 'get_highest_high' src/` → 1 hit, the definition. |

**Trace.** A user creates a 24/7-safe alert with `market_hours_filter{regular_hours: true}`,
reasonably expecting no pages outside 9:30–16:00 ET. The field is never read, so the bot
evaluates every 30 seconds through the night; the moment the sink is wired up they get paged
at 3 a.m. Separately, their `"AAPL ask {{price}} crossed {{threshold}}"` template is delivered
with the literal braces in it.

`MarketHoursFilter.pre_market` / `post_market` are explicitly marked "Not yet implemented" and
are *not* in this table — that's disclosure, not a defect. The three above claim to work.

**Fix.** Either implement them or mark them not-yet-implemented in the proto the same way
`pre_market` is. Right now the contract is making promises the server doesn't keep.

---

### F13 — `last_eval_time` advances even when evaluation failed (MEDIUM · scoped)
`src/bot/alert_bot.rs:76` · `src/alert/alert_engine.rs:210`

The low end of every `[last_eval_time, now]` window is advanced unconditionally, and the code
comment says so on purpose.

```rust
// src/bot/alert_bot.rs:76-77
// Update last_eval_time regardless of evaluation outcome
*self.last_eval_time.lock().await = Some(Utc::now());
```

Three window problems compound here:

1. **Advance-on-failure.** `bar`/`high`/`low` baselines query
   `reduce_bars(…, context.last_eval_time, context.now, …)` (`mod.rs:172,177,182`). If a cycle
   errors — which F7 makes easy, one bad symbol does it — the window it should have covered is
   never re-examined, because `a` has already moved past it. A 5-minute bar whose close
   crossed the threshold during the failed cycle is silently skipped forever.
2. **A gap between windows.** `last_eval_time` is stamped *after* evaluation
   (`alert_bot.rs:77`), while each trigger samples its own `now` at the *start* of its own
   evaluation (`alert_engine.rs:23`). The interval between those two instants — the duration
   of the blocking market-data calls, easily hundreds of milliseconds — falls outside both the
   window that just closed and the one that opens next.
3. **A zero-width first window.** On the very first evaluation `last_eval_time` is `None`, and
   `build_context_map` substitutes `now`:

```rust
// src/alert/alert_engine.rs:210-212
let last_eval_val = last_eval_time
    .map(|t| Value::Timestamp(t.with_timezone(&utc_offset)))
    .unwrap_or_else(|| Value::Timestamp(now.with_timezone(&utc_offset)));
```

   so the first cycle asks for bars in `[now, now]` — an empty range that matches nothing, with
   no indication that it's the degenerate case.

**Trace.** These are latent *today* only because `reduce_bars` is the NaN stub (F4) and returns
the same answer for any window. The moment it's connected to `Bar::get_highest_high`, all three
become live silent-data-loss bugs on the `bar`/`high`/`low` baselines.

**Fix.** Advance `last_eval_time` only on a successful cycle; carry the `now` used by the
evaluation forward as the next window's start rather than re-sampling the clock; and make the
first window explicit (one interval back, or a documented "no history yet" result).

---

### F14 — `DeleteAlert` deletes non-alert bots, and `CreateAlert` can orphan metadata (MEDIUM · scoped)
`src/server/mod.rs:643` · `src/server/mod.rs:617`

Two lifecycle gaps in the new RPCs, both cheap to close.

```rust
// src/server/mod.rs:643-656 — ownership is checked; bot *type* is not
let metadata = self.bot_manager.get_bot_metadata(&request.alert_id).await…
match &metadata.account_identifier {
    Some(id) if id == &expected_identifier => {}
    _ => return Err(Status::permission_denied("Alert does not belong to this account")),
}
self.bot_manager.delete_bot(&request.alert_id).await
```

`delete_alert` never checks that `bot_params` is `AlertBotParams`. Any `bot_id` on the same
account is a valid `alert_id` as far as this handler is concerned — so a client that passes a
trading bot's id to `DeleteAlert` deletes the trading bot. (F2 masks this while the target is
running, which is the only reason it isn't worse.)

Second: `create_alert` writes metadata and then starts the bot as two separate steps.

```rust
// src/server/mod.rs:617-627
let bot_id = self.bot_manager.create_bot("alert", &account_target, bot_config).await
    .map_err(|e| Status::internal(e.to_string()))?;
self.bot_manager.start_bot(&bot_id).await
    .map_err(|e| Status::internal(e.to_string()))?;
```

**Trace.** `create_bot` succeeds — `BotMetadata` is now in Redis with `status: Stopped` — and
`start_bot` then fails (account resolution, `bot_context::BotContext::new`, or the broker
constructor at `bot_context.rs:25`). The client gets `Status::internal` and **never learns the
`alert_id`**. Nothing rolls the metadata back. `resume_bots` only resumes bots whose status is
`Running` (`bot_manager.rs:219`), so the record sits in Redis forever: invisible to the user,
never evaluated, and counted by any future listing.

**Fix.** Check `matches!(metadata.bot_config…, Some(BotParams::AlertBotParams(_)))` in
`delete_alert` before deleting; delete the metadata on a `start_bot` failure in `create_alert`
so the operation is all-or-nothing.

---

## Questions I couldn't answer from the code

These are the ones where I'd be guessing about intent, and each changes a verdict above.

**Q1 — Should a firing be edge-triggered or level-triggered?** This is the single highest-value
answer. If edge, F1 is a HIGH defect requiring persisted per-trigger firing state, and it
interacts with F8 (state doesn't survive restarts, so an edge marker wouldn't either). If
level, F1 drops to a MEDIUM doc fix and `RiseAbove`'s "rises above" wording should change.
Nothing in the code decides this — the proto says both things in different places.

**Q2 — Is `AlertDefinition` meant to be updatable at all?** `UpdateAlert` is `unimplemented`,
but `UpdateBotConfig` reaches the same bot and does swap the definition live. If updates are
in scope, F9 is a real HIGH and per-trigger identity needs designing now. If alerts are meant
to be immutable — delete and recreate — then F9 is latent and the fix is to block
`UpdateBotConfig` on alert bots instead.

**Q3 — Is "no market data yet for this symbol" an error or a normal state?** `latest_quote`
turns `Ok(None)` into an `ExecutionError` (`alert_engine.rs:63-66`). Combined with F7's `?`,
one quiet symbol disables every trigger after it in the list. If it's normal, the fix is in the
CEL function (return an absent/optional value) rather than in the loop.

**Q4 — Is in-memory-only trigger state a deliberate v1 scope cut?** If yes, F8 becomes a doc
fix ("persist" is the wrong word in `alert.proto:20`) plus a decision about what a restart does
to a trailing stop. If no, it's a HIGH and it should land before the sink is wired up, because
that's when a silently-reset water mark starts costing money.

**Q5 — Should `CreateAlert` reject definitions it can't actually evaluate?** Today
`BuiltInTrigger` translation happens at eval time, so an unparseable decimal, an unknown
`time_unit`, or a `bar` baseline routed through the stub all return `Ok` from the RPC and fail
silently forever afterward. Moving translation into `validate_alert_definition` would convert
F3, F5, F4, and half of F11 from silent runtime wrongness into synchronous `400`s. That's a
meaningful architectural change, which is why I'm asking rather than asserting it.

**Q6 — Is the CEL sandbox intended to be the trust boundary?** `NativeTrigger` accepts
arbitrary CEL from any caller by design, and my A7 sweep found no authentication interceptor
on the tonic server (`src/main.rs:137-148`). If the server is only ever reachable on a trusted
network, F11 is a robustness bug and nothing more. If it isn't, the interpolation is the
smaller of two problems and the bigger one is out of scope for this review — worth a
`/security-review` pass either way.

---

## Proposed memory update

Nothing has been written. This repo has no knowledge base at either location, so this would
seed one. **Where do you want it?** `<repo>/.claude/knowledge/` means your teammates and CI
agents get it and it shows up in PR diffs; `~/.claude/projects/-Users-yuhanzhao-GitHub-ninniku/knowledge/`
keeps it local to you. The diff below assumes the repo location. Creating the directory is
itself the record of the choice, so I'll only ask once.

Note what is *not* in here: no `provenance: user` entries, because you haven't confirmed any
intent yet — everything I'd otherwise assert about what this feature is *for* is parked in
`## Open questions` with `asked: never`. Answer Q1–Q6 above and those become invariants with
your words attached, which is the whole point of the exercise.

```diff
diff --git a/dev/null b/.claude/knowledge/INDEX.md
new file mode 100644
--- /dev/null
+++ b/.claude/knowledge/INDEX.md
@@ -0,0 +1,22 @@
+---
+schema: knowledge/v1
+repo: ninniku
+updated: 2026-07-30
+---
+# Knowledge index
+
+Load this file always. Load a domain file when a changed path matches its globs. Load a
+findings ledger only before finalizing a finding in that domain.
+
+| path globs | domain | claims | last verified |
+|---|---|---|---|
+| `src/alert/**`, `src/bot/alert_bot.rs`, `proto/**/alert/**` | [alerting](domains/alerting.md) | 9 | 2026-07-30 @ b00b1d4 |
+
+Findings: [alerting](review/findings/alerting.md) — 14 open, 0 fixed, 0 refuted
+
+## Repo-wide notes
+- Bot metadata is persisted to Redis as base64-encoded protobuf (`src/bot/bot_metadata.rs`),
+  not JSON — proto field removals are wire-breaking for existing records, additions are not.
+- Background tasks (`src/tasks.rs`) are spawned and never restarted; a panicking task is
+  logged only at shutdown. "This panics" therefore means "this component dies silently".
+- `poligun.ninniku.Decimal` is a string with an explicit no-validation contract. Any code
+  path that parses one is a fallback site worth auditing (see TAINT-alerting-001).

diff --git a/dev/null b/.claude/knowledge/domains/alerting.md
new file mode 100644
--- /dev/null
+++ b/.claude/knowledge/domains/alerting.md
@@ -0,0 +1,96 @@
+---
+schema: knowledge/v1
+domain: alerting
+paths: ["src/alert/**", "src/bot/alert_bot.rs", "proto/**/alert/**"]
+updated: 2026-07-30
+head: b00b1d4
+---
+# Alerting
+
+## Intent
+Users define price alerts as a list of triggers evaluated on a shared schedule. Each alert
+runs as its own read-only bot. `BuiltInTrigger`s are structured shorthand that is translated
+into `NativeTrigger` CEL at evaluation time; `NativeTrigger` is raw caller-supplied CEL.
+Per-trigger state round-trips through `TriggerResult.next_state`.
+
+## Lifecycle maps
+
+### MAP-alerting-001 — Alert lifecycle is the bot lifecycle, and delete requires Stopped
+- kind: lifecycle
+- provenance: code
+- status: active
+- anchor: src/bot/bot_manager.rs:191 `Cannot delete a running bot`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'Cannot delete a running bot' src/bot/bot_manager.rs`
+- claim: CreateAlert = create_bot (status Stopped) + start_bot; status becomes Running only
+  after the async BotAckEvent::Started round-trip through bot_manager_loop. delete_bot
+  refuses Running. The alert RPC surface has no stop operation; only the bot-level
+  UpdateBotStatus can stop an alert, and it returns before the status actually flips.
+- matters-because: any claim about alert deletion, or about a state an alert can be left in,
+  has to be checked against this asymmetry rather than against delete_alert alone.
+
+### MAP-alerting-002 — A config update swaps the definition but not the Bot instance
+- kind: lifecycle
+- provenance: code
+- status: active
+- anchor: src/bot/bot_loop.rs:56 `context.update_bot_config(bot_config)`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'create_bot_from_config' src/bot/`
+- claim: BotEvent::ConfigUpdate replaces the BotConfig inside BotContext only.
+  create_bot_from_config runs solely in resume_bot, so the AlertBot struct — and every field
+  on it, including trigger_states and last_eval_time — outlives the definition it was built
+  for. Any per-index or per-definition cache on a Bot is stale after an update.
+- matters-because: turns "the trigger list is effectively immutable" into a false premise;
+  it is the guard that would otherwise refute the positional-state finding.
+
+## Invariants
+
+### INV-alerting-001 — The CEL result contract is a plain map, not a TriggerResult message
+- kind: mechanism
+- provenance: code
+- status: active
+- anchor: src/alert/alert_engine.rs:263 `fn parse_trigger_result`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'fn parse_trigger_result' -A 20 src/alert/alert_engine.rs`
+- claim: the expression must evaluate to Value::Map; `fired` is read only if it is
+  Value::Bool and defaults to false otherwise; `next_state` is read only if it is a Map and
+  is otherwise dropped, leaving the previous state in place. Any other shape degrades to
+  "did not fire" without an error.
+- matters-because: silent-never-fires is the default failure mode of a malformed
+  NativeTrigger, so "no notification" is never evidence that a trigger evaluated correctly.
+
+### INV-alerting-002 — proto doc for NativeTrigger contradicts the implementation
+- kind: mechanism
+- provenance: doc
+- status: active
+- anchor: proto/poligun/ninniku/alert/alert.proto:41 `CEL expression returning TriggerResult`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n "TriggerResult\{" proto/poligun/ninniku/alert/alert.proto`
+- claim: the proto's worked example constructs `TriggerResult{…}` and stores state as
+  `string(new_hwm)`, while the implementation requires a plain map (INV-alerting-001) and
+  the built-in translator stores floats (src/alert/mod.rs:13). Cite as "the contract claims",
+  never as "the requirement is".
+- matters-because: caps at MEDIUM any finding resting on the documented CEL contract.
+
+## Taint sources
+
+### TAINT-alerting-001 — Three request strings are interpolated into CEL source unescaped
+- kind: taint
+- provenance: code
+- status: active
+- anchor: src/alert/mod.rs:32 `format!("{{'fired': price >= decimal('{}')}}"`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n "format!\(\"" src/alert/mod.rs`
+- claim: BuiltInTrigger.symbol, Decimal.value, and BuiltInTrigger.*.time_unit reach ~17
+  format! sites in src/alert/mod.rs with no escaping anywhere in the repo. A single quote
+  restructures the expression. Bounded blast radius: the cel 0.14 stdlib has no file,
+  network, or process primitives, and NativeTrigger already accepts arbitrary CEL from the
+  same RPC — so this is defense-in-depth, not privilege escalation.
+- matters-because: the second half of this claim is what keeps a future review from filing
+  this as CRITICAL RCE; re-check it if NativeTrigger ever becomes privileged.
+
+## Absence claims
+
+### ABS-alerting-001 — No dedup, cooldown, or edge detection exists anywhere
+- kind: absence
+- provenance: code
+- status: active
+- anchor: src/bot/alert_bot.rs:89 `for (i, result) in results.iter().enumerate()`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'cooldown|debounce|throttle|dedup|idempot|already_fired|last_fired|last_sent' src/`
+- claim: as of b00b1d4 the only hits are unrelated. Notification is unconditional on
+  `fired`, once per trigger per cycle. Re-run the verify command every review; never trust
+  this record.
+- matters-because: it is the sole basis for the repeat-fire finding, which is therefore
+  capped at MEDIUM if the verify command ever returns a real hit.
+
+### ABS-alerting-002 — Per-trigger CEL state is never persisted outside process memory
+- kind: absence
+- provenance: code
+- status: active
+- anchor: src/bot/alert_bot.rs:13 `trigger_states: Mutex<Vec<Option<prost_types::Struct>>>`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'trigger_states|next_state' src/ && rg -n 'redis' src/alert/ src/bot/alert_bot.rs`
+- claim: trigger_states lives only on the AlertBot struct. No Redis or Postgres write on that
+  path. resume_bots reconstructs it as vec![None; n].
+- matters-because: every "does it survive a restart" question in this domain resolves to no.
+
+### ABS-alerting-003 — reduce_bars is a NaN stub, disabling more than breakouts
+- kind: absence
+- provenance: code
+- status: active
+- anchor: src/alert/alert_engine.rs:116 `f64::NAN`
+- recorded: 2026-07-30 @ b00b1d4 (branch cel-alert)
+- verify: `rg -n 'reduce_bars' src/alert/ && rg -n 'get_highest_high' src/`
+- claim: reduce_bars returns NaN unconditionally. It backs BreakoutAbove/BreakoutBelow *and*
+  the high, low, and bar baselines (src/alert/mod.rs:171-185), so 3 of 6 baseline types are
+  silently non-functional for every trigger type. The in-file comment understates this.
+  Bar::get_highest_high (src/postgres/bar.rs:200) is the intended replacement and has no
+  caller.
+- matters-because: while this holds, every window/boundary finding on bar-based baselines is
+  latent rather than live. When it stops holding, they all go live at once.
+
+## Open questions
+
+### Q-alerting-001 — Is firing edge-triggered or level-triggered?
+- proposed answer (inferred, unconfirmed): edge — "rises above" / "falls below" in
+  alert.proto:117-163 is transition language, and TriggerResult.next_state exists to make
+  edge tracking expressible.
+- would change: severity of the repeat-fire finding (HIGH if edge, MEDIUM doc-fix if level),
+  and whether RiseAbove/FallBelow need to emit next_state at all.
+- asked: never
+
+### Q-alerting-002 — Is an AlertDefinition meant to be updatable in place?
+- proposed answer (inferred, unconfirmed): yes — UpdateAlert is declared in ninniku.proto,
+  and UpdateBotConfig already reaches an alert bot's definition today.
+- would change: whether positional trigger_states is a live HIGH or a latent design finding,
+  and whether triggers need stable ids.
+- asked: never
+
+### Q-alerting-003 — Should CreateAlert reject definitions it cannot evaluate?
+- proposed answer (inferred, unconfirmed): yes — translating BuiltInTriggers at create time
+  rather than eval time would convert several silent runtime failures into synchronous
+  InvalidArgument responses.
+- would change: severity of the decimal-fallback, time_unit-fallthrough, and stubbed-baseline
+  findings — all drop substantially if the RPC rejects them up front.
+- asked: never
```

I'd also propose seeding `.claude/knowledge/review/findings/alerting.md` with the 14 findings
above as `FND-alerting-001..014` in the `## Open` section, so the next review references them
instead of re-deriving them. I've left that out of the diff to keep it readable — say the word
and I'll include it.

Say which location you want (or "skip") and I'll write it. If you'd rather not have this in
the repo at all, that's fine — I won't re-ask this session.
