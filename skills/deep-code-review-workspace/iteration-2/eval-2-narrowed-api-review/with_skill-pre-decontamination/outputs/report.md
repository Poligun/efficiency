# Review: cel-alert → origin/HEAD (merge-base e85ca8d)

This branch adds a CEL-expression alerting subsystem: a new `poligun.ninniku.alert` proto package (`NativeTrigger` + `BuiltInTrigger`, `EvalSchedule`, `Sink`, `AlertDefinition`), an `AlertBotParams` variant on `BotConfig`, and `CreateAlert`/`UpdateAlert`/`DeleteAlert` on the `Ninniku` service. The contract is well-organized and unusually well-commented — but it is substantially ahead of its implementation, and the gap is undisclosed. Six declared capabilities (notification delivery, `{{binding}}` templating, `required_symbols` subscription, `market_hours_filter`, `initial_state` seeding, and every bar-derived trigger) are documented as working and are not. The author demonstrably knows how to disclose a stub, because `MarketHoursFilter.pre_market` carries `// Not yet implemented.` — which is exactly what makes the silence everywhere else read as a promise. To answer your question directly: the shape of the API is mostly sound, but if another team generates a client from this file today, most of what they build against does nothing, and two modelling choices (`time_unit` as a string, no firing-semantics field) will cost a breaking change to fix once they have.

**Coverage.** Only the **wire-contract (proto) aspect** ran, at your request. `code_api` (the new `src/alert/` and `src/bot/alert_bot.rs` Rust surface), `logic` (business-logic review of the evaluation engine), and `convention` (whether the new modules match repo patterns) were all detected as active and **skipped** — so this report says nothing about the quality of the implementation itself. I did *read* `src/` extensively, because judging whether a contract is honest requires grepping for a consumer; every finding is anchored in a `.proto` file, and implementation defects the contract doesn't misrepresent are deliberately not reported. One reviewer agent plus twelve verifiers ran; all twelve verification slots were used and all twelve returned. Three findings are therefore `unverified` — F4, F9, and F12; I confirmed F4 and F9 first-hand by reading both sides, F12 rests on reading the service definition. Findings are capped at 15, and one MEDIUM (`EvalSchedule.interval` has no documented lower bound) was cut to the design notes to stay under it; design notes are all unverified. Blast-radius searches covered this repo only, including the checked-in `ninniku-fe/` TypeScript client — I cannot see other repos.

---

## Needs a decision before merge

### D1 — No way to express one-shot or cooldown firing semantics (HIGH · needs-decision · grounded)
`proto/poligun/ninniku/alert/alert.proto:224`

`AlertDefinition` carries `triggers`, `eval_schedule`, `sink`, `required_symbols` — and nothing governing *repeat* firing. A grep across `proto/`, `src/alert/`, and `src/bot/` for `cooldown|one_shot|auto_disable|latch|dedup|throttle` returns zero hits. All six `BuiltInTrigger` variants translate to level predicates re-evaluated fresh each tick with no edge detection: once AAPL crosses 200, `{'fired': price >= decimal('200')}` is true on every subsequent evaluation, and the dispatch loop notifies on every one of them. At the contract's own documented cadence — `E.g. { seconds: 5 }` — that is a notification every five seconds until the alert is deleted.

```
  // One or more triggers evaluated on each tick. The alert fires (dispatches
  // to sink) when any trigger returns TriggerResult{fired: true}.
  repeated TriggerConfig triggers = 1;
```

The trailing variants do set `next_state`, but only to walk the water mark — that isn't a latch, so they re-fire every tick too once price is past the threshold. Blast radius today is zero because delivery is stubbed (F1), which is why this is HIGH rather than CRITICAL. It is pinned because `fired: true` becomes load-bearing for every client the moment delivery lands, and changing what it means afterwards is not additive.

**Open question.** One-shot (auto-stop after first fire), a cooldown duration, or edge-triggered (fire only on the false→true transition)? The answer decides whether the field belongs on `AlertDefinition` or per-`TriggerConfig`, so it has to be settled before the shape is published.

### D2 — `time_unit` is a free-form string where `marketdata.TimeUnit` already exists (HIGH · needs-decision · grounded)
`proto/poligun/ninniku/alert/alert.proto:154`

`time_unit` is declared as `string` in three places in the new package, documented only by `// e.g. "MINUTE"`. The repo already has a `TimeUnit` enum, and `ninniku.proto` — the same file that imports `alert.proto` — uses it as a typed field two RPCs away. The parser accepts anything and falls back silently:

```
proto/poligun/ninniku/alert/alert.proto:152-154
    int32  lookback_bars = 1;
    int32  multiplier    = 2;
    string time_unit     = 3;

proto/poligun/ninniku/ninniku.proto:85
  poligun.ninniku.marketdata.TimeUnit time_unit = 3;

src/alert/mod.rs:207-211
    let unit_seconds: i32 = match time_unit.to_uppercase().as_str() {
        "MINUTE" => 60,
        "HOUR" => 3600,
        _ => 60,
    };
```

A client sending `"DAY"`, `"1Min"`, or `"minute "` gets a lookback window computed in minutes, with no error at create time and none at evaluation time. Because `string` is length-delimited and an enum is a varint, converting these fields later on the same field numbers is wire-breaking — this is the change that is free now and costs a migration once other teams have generated clients. (The verifier argued for MEDIUM on the grounds that nothing is wire-broken *today*, since `alert.proto` is net-new. I'm keeping HIGH: "nothing consumes it yet" is precisely the window you asked about, and it closes the moment this merges.)

**Open question.** `marketdata.TimeUnit` currently defines only `TIME_UNIT_UNKNOWN` and `TIME_UNIT_MINUTE`, yet the alert translator already handles `HOUR` and `BarField` implies more. Extend the shared enum (`TIME_UNIT_HOUR`, `TIME_UNIT_DAY`) and reuse it, or give the alert subsystem its own? Either is fine; leaving it a string is the option that can't be undone.

---

## Findings

### F1 — `Sink` is required and validated, but nothing is ever delivered (CRITICAL · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:231`

`AlertDefinition` states the alert "fires (dispatches to sink)" when a trigger returns `fired: true`, the server *rejects* a definition without a sink, and `Sink` offers exactly one transport. The entire delivery path is a log line. A repo-wide case-insensitive grep for `telegram` in `src/` returns three lines, all in `alert_bot.rs` — the template-extraction match arm, the TODO, and the warning. No Bot API client, no token config, no outbound call of any kind.

```
proto/poligun/ninniku/alert/alert.proto:231
  Sink sink = 3;

src/bot/alert_bot.rs:105-107
            // TODO: deliver via Telegram when Sink support is wired up
            info!("AlertBot: trigger {} fired — {}", i, message);
            warn!("AlertBot: Telegram notification not yet implemented");
```

A caller working from the proto creates an alert, gets an `alert_id` and a `BOT_STATUS_RUNNING` bot, and is never notified — no error at creation, none at evaluation. The same message carries a second undisclosed promise: `TelegramNotification.message_template` documents `{{name}}` binding substitution with a worked example (`alert.proto:210-212`), and `alert_bot.rs:99` clones the template verbatim. Binding values never leave the CEL evaluation context — `TriggerResult` exposes only `fired`, `next_state`, `message` — so no code path anywhere is capable of performing the substitution.

**Fix.** Either implement delivery, or disclose it in the contract the way `pre_market` is disclosed. The asymmetry is the problem: one stub in this file is marked and five are not, so the marking reads as meaningful.

### F2 — `NativeTrigger.initial_state` is documented as seed state and is never read (HIGH · mechanical · grounded)
`proto/poligun/ninniku/alert/alert.proto:53`

The field promises it seeds `context.state` for the first evaluation. Every state slot is initialized to `None` and `initial_state` is never consulted — its only occurrence in `src/` is a *write* in the built-in translation path. No `.or_else`, no first-evaluation branch.

```
proto/poligun/ninniku/alert/alert.proto:51-53
  // Seed state for the very first evaluation, accessible as context.state["key"].
  // On subsequent evaluations, TriggerResult.next_state takes precedence.
  optional google.protobuf.Struct initial_state = 4;

src/bot/alert_bot.rs:21
            trigger_states: Mutex::new(vec![None; trigger_count]),
```

A client seeding a high-water mark — the exact use case the surrounding comments describe — sees an empty `context.state` on the first tick and arms the trigger against the wrong reference price. Nothing rejects or warns about the ignored field.

**Fix.** Seed the state vector from each trigger's `initial_state` at bot construction, or delete the field.

### F3 — The contract's own `NativeTrigger` example uses syntax the evaluator rejects (HIGH · mechanical · grounded)
`proto/poligun/ninniku/alert/alert.proto:42`

The doc block hands external teams a worked example whose expression returns `TriggerResult{...}` — CEL message-construction syntax. The evaluator requires a plain CEL map and errors otherwise; and the `cel` 0.14 crate is pulled in without its `structs` feature, so `Ident{...}` fails with "feature not enabled" before type lookup is even reached. Nothing in `src/` registers a struct type with the CEL context.

```
proto/poligun/ninniku/alert/alert.proto:41-45
  //   TriggerResult{
  //     fired: price <= new_hwm - decimal('1.00'),
  //     next_state: {'hwm': string(new_hwm)}
  //   }

src/alert/alert_engine.rs:264-271
    let map = match value {
        Value::Map(ref m) => m,
        _ => {
            return Err(format!(
                "Expression must return a map with 'fired' key, got: {:?}",
                value
            ))
```

The first thing another team copies out of this file produces a trigger that errors on every tick and never fires. The example is wrong a second way: it stores state as `string(new_hwm)`, while the repo's own translator writes `{'hwm': new_hwm}` and its comment says "State is stored as a float" — so a client that fixes the map syntax still hits a type mismatch on the second evaluation.

**Fix.** Rewrite the example as the map literal the engine accepts, with float state values, and drop the "returning TriggerResult" phrasing at `alert.proto:12` and `:46` — the CEL contract is a map whose keys mirror `TriggerResult`, not the message itself.

### F4 — `UpdateAlert` is documented as working and returns UNIMPLEMENTED (HIGH · mechanical · unverified)
`proto/poligun/ninniku/ninniku.proto:67`

The service block documents the RPC with no caveat and defines a full request message carrying `account_target`, `alert_id`, and `alert_definition`. The handler returns unconditionally:

```
proto/poligun/ninniku/ninniku.proto:66-67
  // Replace the AlertDefinition of an existing alert.
  rpc UpdateAlert (UpdateAlertRequest) returns (UpdateAlertResponse);

src/server/mod.rs:632-637
    async fn update_alert(
        &self,
        _request: Request<UpdateAlertRequest>,
    ) -> Result<Response<UpdateAlertResponse>, Status> {
        Err(Status::unimplemented("UpdateAlert not yet implemented"))
    }
```

A team building an alert-editing UI against this contract ships it and finds at runtime that the only way to change an alert is delete-then-create — which mints a new `alert_id` and invalidates any id they persisted. The verification budget was spent before this one; I read both sides directly, but no independent agent checked it.

**Fix.** Mark it unimplemented in the proto until the handler exists. Separately, when it is implemented the contract needs to say what happens to accumulated per-trigger state on update — for a trailing trigger, silently resetting the water mark changes when the alert fires.

### F5 — A malformed `Decimal` becomes a threshold of 0.0 and the alert fires forever (HIGH · scoped · grounded)
`proto/poligun/ninniku/well_known_types.proto:7`

This branch adds a doc comment committing the API to performing no validation on `Decimal` strings — and `Decimal` carries every alert threshold and water mark. On the alert path the string is parsed with a silent zero fallback:

```
proto/poligun/ninniku/well_known_types.proto:7-9
// The value should be a string representation of a decimal number, e.g. "123.45". The API will not perform any
// validation on the format of the string, so it is the responsibility of the client to ensure that it is a valid
// decimal number.

src/alert/alert_engine.rs:31-36
    ctx.add_function("decimal", |s: Arc<String>| -> f64 {
        s.parse::<f64>().unwrap_or_else(|_| {
            warn!("decimal(): failed to parse '{}', returning 0.0", s);
            0.0
        })
    });
```

A `RiseAbove.price` of `"$200"` or `"1,250.00"` — both plausible from a UI — becomes `price >= 0.0`, true on every evaluation, forever, with only a server-side warning. Nothing between the RPC boundary and CEL evaluation inspects the string: `validate_alert_definition` checks only that `triggers` is non-empty and that `eval_schedule.interval` and `sink` are present.

Two adjacent problems on the same line. The value is interpolated into CEL *source* via `format!("... decimal('{}') ...", price.value)` with no escaping, so a `Decimal` containing a quote alters the expression's structure rather than its value. And the same commit's claim that `Decimal` exists to represent numbers "without losing precision" is contradicted by this path, which converts both sides of every comparison to `f64`.

**Fix.** This is the one place "the client is responsible" isn't tenable, because the failure is silent and unbounded. Validate the format at the RPC boundary and reject, or make `decimal()` propagate a parse error instead of returning 0.0. Either way, escape or reject quote characters before interpolation.

### F6 — Every bar-derived trigger can never fire, and the contract doesn't say so (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:151`

`reduce_bars` is a stub returning NaN precisely so comparisons fail. The proto states the affected triggers fire, with no unimplemented marker — while `MarketHoursFilter` a few sections later carries one.

```
proto/poligun/ninniku/alert/alert.proto:149-151
  // Fires when the baseline price exceeds the highest high of the last
  // lookback_bars completed bars.
  message BreakoutAbove {

src/alert/alert_engine.rs:98-99, 114-116
    // --- reduce_bars: stub — bar range queries not yet in MarketData trait.
    //     Returns sentinel values so breakout triggers silently never fire.
            // NaN is the safe sentinel: all IEEE 754 comparisons against NaN return false,
            // so no trigger fires regardless of direction or baseline type.
            f64::NAN
```

The reach is wider than the breakout messages: `BreakoutAbove` and `BreakoutBelow` are dead unconditionally (2 of 6 `trigger_type` variants), and **3 of the 6 `Baseline` variants** route through the same stub — `high`, `low`, *and* `bar`, the explicit OHLCV `BarField` selector. So the other four trigger types are dead too whenever they are paired with one of those baselines. Only `ask`, `bid`, and `trade` baselines work. `CreateAlert` accepts all of them without complaint, and the alert sits `RUNNING` forever. The implementation comment says "silently never fire" in as many words; the contract says the opposite.

**Fix.** Mark both breakout messages and the `high`/`low`/`bar` baselines `// Not yet implemented.`, or reject them in `validate_alert_definition` so the failure is loud at create time rather than invisible at run time.

### F7 — `required_symbols` promises a subscription the engine never makes (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:238`

The comment documents this as the mechanism by which the engine subscribes to market data, and tells clients it is the *only* symbol source for `NativeTrigger`s. The field has no reader anywhere in the repo.

```
proto/poligun/ninniku/alert/alert.proto:233-238
  // Symbols required across all triggers. The engine subscribes to market
  // data for these symbols once for the whole alert.
  // For BuiltInTrigger, this must include BuiltInTrigger.symbol.
  // For NativeTrigger, this is the only source of symbol information since
  // CEL expressions are opaque at parse time.
  repeated string required_symbols = 4;
```

Market data reaches the engine only through a passive Postgres-backed cache populated by a separate Redis watchlist and the global `Subscribe` RPC. A client that correctly populates `required_symbols` for a symbol not already in that unrelated set gets `latest_quote` returning "no data for symbol", which aborts the whole definition for that tick and is logged server-side only — the alert reads `RUNNING` and silently does nothing.

**Fix.** Have `CreateAlert` subscribe to `required_symbols`, or drop the field and document that clients must call `Subscribe` themselves. The current text promises the former.

### F8 — `market_hours_filter` has no reader; `regular_hours` is silently ignored (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:193`

`EvalSchedule` tells clients an absent filter means the alert "always evaluates", which is only worth saying if a present filter restricts evaluation. `MarketHoursFilter` then marks `pre_market` and `post_market` as not implemented — and says nothing about `regular_hours`, so a client reads it as working. Grepping `src/` for `market_hours_filter`, `MarketHoursFilter`, `regular_hours`, and `market_hours` returns zero matches; `AlertBot` reads only `eval_schedule.interval`.

```
proto/poligun/ninniku/alert/alert.proto:186-187
  // If absent, the alert always evaluates (suitable for 24/7 assets).
  optional MarketHoursFilter market_hours_filter = 2;

proto/poligun/ninniku/alert/alert.proto:193-197
  bool regular_hours = 1;

  // Not yet implemented.
  bool pre_market  = 2;
```

An equities alert configured for regular hours only evaluates around the clock and fires at 3am on stale overnight quotes.

**Fix.** Gate the evaluation loop on the filter, or extend the existing `// Not yet implemented.` to cover `regular_hours` too.

### F9 — `Alert` is unreferenced and its comment contradicts `AlertBotParams` (MEDIUM · mechanical · unverified)
`proto/poligun/ninniku/alert/alert.proto:241`

```
proto/poligun/ninniku/alert/alert.proto:241-245
// Full alert record stored in AlertBotParams. alert_id is server-assigned.
message Alert {
  string          alert_id   = 1;
  AlertDefinition definition = 2;
}

proto/poligun/ninniku/bot/bot.proto:44-46
message AlertBotParams {
  poligun.ninniku.alert.AlertDefinition definition = 1;
}
```

`AlertBotParams` stores an `AlertDefinition`, not an `Alert`; the id lives on `BotMetadata.bot_id`. No RPC, field, or Rust call site references the `Alert` type — `grep -rn 'alert::Alert\b' src/` is empty. A team reading this file models their client around an `Alert` record with an `alert_id` that no response ever returns, and looks for that id inside the stored params, where it isn't.

**Fix.** Delete `Alert`, or make it the return type of the read operation F12 is about — but correct the comment either way, since it is wrong as it stands.

### F10 — `can_trade` states a uniqueness invariant that `UpdateBotConfig` doesn't enforce (MEDIUM · scoped · grounded)
`proto/poligun/ninniku/bot/bot.proto:19`

The new field's comment publishes a system invariant. That check runs only in `create_bot`; `update_bot_config` rewrites `bot_config` and carries the rest of the metadata forward untouched, so it neither re-derives `can_trade` nor re-runs the uniqueness check.

```
proto/poligun/ninniku/bot/bot.proto:18-20
  // True if this bot can submit orders. At most one trading bot may be registered per account;
  // read-only bots (e.g. AlertBot) have no such limit.
  bool can_trade = 7;

src/bot/bot_manager.rs:166-169
        let new_metadata = BotMetadata {
            bot_config: Some(bot_config.clone()),
            ..metadata
        };
```

The bypass is reachable today because `bot_can_trade` treats everything that isn't an `AlertBotParams` as trade-capable (`bot_manager.rs:285-287`). Create two alerts on one account — both exempt, since `can_trade` is false — then `UpdateBotConfig` each to `NoOpBotParams`. Neither update re-derives the flag or re-checks uniqueness, so the account ends with two bots the codebase's own predicate classifies as trade-capable, both reporting `can_trade: false` through `GetBotMetadata`. A client gating its trading UI on this field shows the wrong thing.

I lowered this from HIGH on the verifier's evidence: neither implemented bot variant actually submits orders today, so this is a labelling and invariant violation rather than live trading risk — and `create_bot` does re-scan live configs, so a mixed update-then-create sequence *is* caught. It returns to HIGH the day a real order-submitting variant is added. Note also that the server already distrusts the stored value: `bot_manager.rs:116` re-derives it rather than reading field 7.

**Fix.** Re-derive `can_trade` and re-check uniqueness in `update_bot_config`. In the proto, either document the field as output-only and server-derived, or stop stating the invariant on it.

### F11 — `DeleteAlert`'s `account_target` check is bypassed by the generic bot RPCs (MEDIUM · scoped · grounded)
`proto/poligun/ninniku/ninniku.proto:239`

`DeleteAlertRequest` takes an `account_target` and the handler enforces it, returning `permission_denied` when the alert belongs to another account. But `CreateAlertResponse.alert_id` is documented as "Also used as the underlying AlertBot's bot_id", and `DeleteBotRequest` takes a bare `bot_id` with no account at all — and neither the handler nor `bot_manager.delete_bot` checks ownership. `UpdateBotConfig` has the same shape.

```
proto/poligun/ninniku/ninniku.proto:238-241
message DeleteAlertRequest {
  poligun.ninniku.account.AccountTarget account_target = 1;
  string                                alert_id       = 2;
}

proto/poligun/ninniku/ninniku.proto:214-216
message DeleteBotRequest {
  string bot_id = 1;
}
```

To be precise about what this is and isn't: the service has no authentication layer — the gRPC stack in `main.rs` is CORS plus grpc-web plus tracing — and `AccountTarget` selects among server-configured brokerage accounts rather than identifying a caller. So this is not a security bypass; nobody gains access they didn't have. It is an API-consistency defect: the branch introduced an account-alignment invariant on one RPC while an equivalent older RPC addressing the same resource silently skips it, so which guarantee holds depends on which method the client happened to call.

**Fix.** Decide whether alerts are addressed by `(account_target, alert_id)` or by bare `bot_id`, and make both paths agree — either add `account_target` to the bot RPCs or drop the check from `DeleteAlert`.

### F12 — Alerts have Create/Update/Delete but no read operation (MEDIUM · needs-decision · unverified)
`proto/poligun/ninniku/ninniku.proto:64`

`CreateAlert` returns an `alert_id` and there is no `GetAlert` or `ListAlerts`. The only read path is the generic bot surface: `GetBotStatusesRequest` is empty — it returns every bot id in the service with no account scoping — and `GetBotMetadata` is per-id. A frontend rendering "my alerts" must fetch all bot ids system-wide, call `GetBotMetadata` on each, and filter on `bot_params` being `alert_bot_params`.

```
proto/poligun/ninniku/ninniku.proto:174-178
message GetBotStatusesRequest {}

message GetBotStatusesResponse {
  // Map from bot ID to BotStatus
  map<string, poligun.ninniku.bot.BotStatus> bot_statuses = 1;
}
```

The definition *is* recoverable — `BotMetadata.bot_config` carries `AlertBotParams` — so this is a usability and scoping problem, not data loss. But it sits oddly next to `DeleteAlert`, which goes out of its way to enforce account ownership on the same resources this path enumerates without any filter.

**Open question.** Are alerts a first-class resource with their own `ListAlerts(account_target)` / `GetAlert`, or a projection of the bot surface? If the latter, `GetBotStatuses` needs account scoping and a way to identify alert bots without fetching every metadata record. This is the same question that decides whether `Alert` (F9) should exist.

### F13 — Two `AccountInfo` fields are removed, inside a dependency-bump commit (MEDIUM · needs-decision · grounded)
`proto/poligun/ninniku/alpaca/account_info.proto:31`

```
proto/poligun/ninniku/alpaca/account_info.proto:31
  reserved 7; // Was pattern_day_trader

proto/poligun/ninniku/alpaca/account_info.proto:59
  reserved 21; // Was daytrade_count
```

The `reserved` ritual is correct and no field number is reused — that part is right, and the Rust side genuinely stops populating both fields, so this is a real removal rather than a dead-code cleanup. Two things about it aren't right. First, nothing in the alert subsystem touches `AccountInfo`, and the change doesn't merely ride in the wrong branch — it rides in commit `aad07b3`, whose message is "Bump dependnecies". A wire-breaking field removal buried in a dependency bump is close to invisible to review. Second, the removal breaks in the silent direction: deployed clients keep decoding successfully and see `patternDayTrader = false` and `daytradeCount = 0` rather than an error. Searching the whole repo, the only reference left is the checked-in generated TypeScript client, which still declares both fields at `ninniku-fe/src/generated/poligun/ninniku/alpaca/account_info.ts:159,173` and defaults them at `:183,189`; no hand-written frontend code reads them today. For a trading UI, PDT status silently reading `false` is the worst available default. I cannot see consumers outside this repo.

**Open question.** Why are these fields going away, and does that belong in `cel-alert` — let alone in a commit titled "Bump dependnecies"? If the removal is intended, split it into its own commit and regenerate `ninniku-fe` in the same change so the silent-default window never exists. Minor addendum, honestly weaker than it first looked: the numbers are reserved but the names are not, which normally endangers JSON and proto-text consumers — but this API is consumed over binary grpc-web, so `reserved "pattern_day_trader", "daytrade_count";` is cheap insurance rather than an active hazard.

---

## Design notes

Opinions and lower-confidence observations, unranked and unverified.

- **`build.rs` drops serde derives from the entire `.poligun.ninniku.bot` package**, not just the alert-carrying types (`build.rs:10`). It's forced — `AlertBotParams` transitively contains `prost_types::Struct`, which doesn't implement serde — and I found no broken consumer, since bot metadata persists via prost + base64. But `.poligun.ninniku.account` keeps serde while `.poligun.ninniku.bot`, which embeds account types, has lost it, and the next person to try a JSON dump of bot config hits a non-obvious compile error.
- **`EvalSchedule.interval` has no documented or enforced lower bound** (`alert.proto:184`). Validation checks presence only and the bot loop rejects only non-positive durations, so `{ nanos: 1 }` yields a near-continuous evaluation loop issuing a cache lookup per trigger. Cut from the findings list to stay under the cap.
- **The `high`/`low` baselines are documented as "session high"/"session low"** (`alert.proto:87-88`) but the translator windows `reduce_bars` from `context.last_eval_time` to `context.now` — the ~5 second gap since the last tick. This drift lives in the caller's window arguments, not the stub, so fixing `reduce_bars` would not fix it: a "session high" baseline would then compare against a five-second high and fire on nearly every tick.
- **A present `MarketHoursFilter` with all fields defaulted means "never evaluate"** (`alert.proto:192-198`). The contract says what absence means but not what an all-false filter means, and proto3 gives no way to distinguish "set to false" from "not set".
- **`NativeTrigger.parameters` is `map<string, Value>` while `initial_state` and `next_state` are `Struct`** (`alert.proto:49` vs `:53`) — `Struct` is exactly `map<string, Value>`, so the same shape is spelled two ways in one message, and `EvalContext` mirrors the split.
- **There is no way to clear trigger state.** Omitting `next_state` means carry-forward (`alert.proto:20-22`), so a CEL expression can add to state and replace it but never reset it to empty.
- **For a `BuiltInTrigger`, the binding names a `{{name}}` template could reference are internal and undocumented** — `price`, `prev_hwm`, `new_hwm`, `bar_high` — so even once templating exists (F1), a client cannot write a template for a built-in trigger from the contract alone.
- **`EvalContext` is declared "never wire-exchanged"** (`alert.proto:64-70`). That's honest disclosure and I'm not flagging it, but it still generates a type in every client language, so it will appear in other teams' code completion as if it were a message they should send.

## Could not resolve

- **Whether anything outside this repo reads `AccountInfo.pattern_day_trader` or `daytrade_count`** (F13). I searched this repo including the checked-in frontend and found only the stale generated client. Settling it needs a search across the other repos that generate from these protos, or a look at what actually calls `GetAccountInfo` in production.
