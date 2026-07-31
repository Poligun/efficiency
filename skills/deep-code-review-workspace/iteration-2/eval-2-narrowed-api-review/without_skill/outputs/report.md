# API review — proto changes on `cel-alert`

Scope: the `.proto` surface only (`git diff main...HEAD -- proto/`). Implementation was read only where the proto's own comments make a claim about runtime behavior that other teams would code against.

Files reviewed:
- `/Users/yuhanzhao/GitHub/ninniku/proto/poligun/ninniku/alert/alert.proto` (new, 245 lines)
- `/Users/yuhanzhao/GitHub/ninniku/proto/poligun/ninniku/ninniku.proto` (3 new RPCs + 6 messages)
- `/Users/yuhanzhao/GitHub/ninniku/proto/poligun/ninniku/bot/bot.proto` (`AlertBotParams`, `can_trade`)
- `/Users/yuhanzhao/GitHub/ninniku/proto/poligun/ninniku/well_known_types.proto` (doc comment)
- `/Users/yuhanzhao/GitHub/ninniku/proto/poligun/ninniku/alpaca/account_info.proto` (two field removals — unrelated to alerts)

## Verdict

The core modeling is good. `TriggerConfig` as a oneof over `BuiltInTrigger`/`NativeTrigger`, `TriggerResult` as a versionable return envelope, and the state-carry protocol (`initial_state` → `next_state` → `context.state`) are the right shapes and will age well. `AlertDefinition` split out from `Alert` so it can be reused across create/update is correct.

But **it is not ready for other teams to build against yet.** There are four blockers, and three of them are the kind that get baked in permanently once a second client exists:

1. The documented CEL return contract is wrong — the example does not run.
2. There is no read path at all — clients cannot list or fetch their own alerts.
3. Roughly a third of the declared trigger surface is a silent no-op at runtime.
4. `time_unit` is a bare `string` when the repo already has a `TimeUnit` enum.

Fixing 1, 3, and 4 is nearly free today and expensive after other teams ship. Fixing 2 is additive so it can follow, but if you don't add it now, teams will build the `GetBotStatuses` workaround and you will be supporting that forever.

---

## Blockers

### B1. The documented CEL contract does not match the evaluator — the example in the proto cannot run

`NativeTrigger.expression` is documented as:

> CEL expression returning TriggerResult.

with the example:

```
TriggerResult{
  fired: price <= new_hwm - decimal('1.00'),
  next_state: {'hwm': string(new_hwm)}
}
```

The evaluator does not accept a `TriggerResult` message. `parse_trigger_result` in `/Users/yuhanzhao/GitHub/ninniku/src/alert/alert_engine.rs:263` requires the expression to return a **CEL map**, and reads the string keys `fired`, `message`, `next_state`:

```rust
let map = match value {
    Value::Map(ref m) => m,
    _ => return Err(format!("Expression must return a map with 'fired' key, got: {:?}", value))
};
```

The cel-rust interpreter has no proto message construction, so `TriggerResult{...}` is not expressible at all — the documented example fails to parse. The proto comment is the contract here; every team writing their first `NativeTrigger` will copy that example and get an error.

Also note the example is internally inconsistent: it uses message-construction syntax for the outer value and map-literal syntax for the nested `next_state`.

Fix — pick one and make it true:
- **Preferred:** change the comment to specify a map contract and give a working example:
  ```
  // CEL expression returning a map with keys:
  //   fired      (bool, required — absent or non-bool is treated as false)
  //   next_state (map<string, dyn>, optional)
  //   message    (string, optional)
  // Example (trailing stop):
  //   {'fired': price <= new_hwm - decimal('1.00'),
  //    'next_state': {'hwm': string(new_hwm)}}
  ```
  Then keep the `TriggerResult` message purely as the documented schema of that map, and say so explicitly — the same way `EvalContext` already does.
- Or register `TriggerResult` in the CEL type provider so the documented syntax actually works.

Either way, also document the failure modes that are currently silent: a non-map return errors, but a map missing `fired`, or with a non-bool `fired`, silently becomes `fired: false` (`alert_engine.rs:274-278`). An alerting product where a typo means "never fires, no error" needs that stated in the contract at minimum.

### B2. No read path — Create/Update/Delete with no Get or List

`ninniku.proto:59-70` adds `CreateAlert`, `UpdateAlert`, `DeleteAlert`. There is no `GetAlert` and no `ListAlerts`.

A client that creates an alert holds an `alert_id` only for that session. A fresh page load cannot render "your alerts" at all. The only workaround is `GetBotStatuses` → for each bot `GetBotMetadata` → unwrap `BotConfig.alert_bot_params.definition` — which leaks the bot abstraction that `CreateAlert` exists to hide, requires the client to know which bots happen to be alert bots, and gives no way to filter by `account_target` (`GetBotStatusesRequest` is empty).

This is additive so it isn't a wire break to add later, but it is a **de facto** break: the first two teams will implement the bot-walking workaround and it becomes the real API.

```proto
message ListAlertsRequest  { poligun.ninniku.account.AccountTarget account_target = 1; }
message ListAlertsResponse { repeated poligun.ninniku.alert.Alert alerts = 1; }
message GetAlertRequest    { poligun.ninniku.account.AccountTarget account_target = 1; string alert_id = 2; }
message GetAlertResponse   { poligun.ninniku.alert.Alert alert = 1; }
```

This also gives the currently-dead `Alert` message (see M5) a job.

### B3. A third of the declared surface is a documented no-op

Three groups of fields are in the schema and will show up in every generated client, but do nothing:

- **`MarketHoursFilter.pre_market` / `post_market`** — the proto says "Not yet implemented." A client can set `pre_market: true` and gets no error and no pre-market evaluation.
- **`Baseline.high` / `Baseline.low`** and **`BreakoutAbove` / `BreakoutBelow`** — all four route through `reduce_bars`, which is a stub (`/Users/yuhanzhao/GitHub/ninniku/src/alert/alert_engine.rs:98-118`). It returns `f64::NAN`, and the comment is explicit about the consequence: *"Returns sentinel values so breakout triggers silently never fire."*

That's 2 of 6 baseline variants and 2 of 6 trigger types that accept configuration, report success, and then never fire. NaN-poisoning is a reasonable *implementation* choice, but as an *API* choice "accepted and silently inert" is the worst of the three options.

Pick one before publishing:
- `reserved` the field numbers and add them when they work (cleanest — nothing to un-teach later); or
- keep them in the schema but have the server reject them with `INVALID_ARGUMENT: not yet implemented`, and say so in the comment. Loud beats silent for alerting.

Right now a team will build a breakout-alert UI on top of a feature that cannot fire.

### B4. `time_unit` is a bare `string` in three places

`Baseline.BarField.time_unit`, `BreakoutAbove.time_unit`, `BreakoutBelow.time_unit` are all `string`, commented `// e.g. "MINUTE"`.

The repo already has the right type: `poligun.ninniku.marketdata.TimeUnit` (`marketdata.proto:13-16`), used by `GetBarsRequest.time_unit` and `GetRenkoChartsRequest.time_unit`. This new file is the only place that goes stringly-typed.

Costs: no codegen constants for clients, no client-side validation, undefined case-sensitivity (`"MINUTE"` vs `"minute"` vs `"Minute"`), no compile-time break when the enum gains `TIME_UNIT_HOUR`/`TIME_UNIT_DAY`. The string is passed straight through into a generated `reduce_bars(...)` CEL call (`/Users/yuhanzhao/GitHub/ninniku/src/alert/mod.rs:127`), so whatever clients send becomes load-bearing.

Change to `poligun.ninniku.marketdata.TimeUnit`. Free now; a wire-type change (`string` → `enum`) later.

---

## Should fix before other teams start

### M1. The precision guarantee stops at the CEL boundary, and only an example says so

This branch adds a strong doc comment to `well_known_types.proto`: `Decimal` is a string wrapper "to represent decimal numbers without losing precision… used for all price and quantity fields in the API." `BuiltInTrigger` honors it (`RiseAbove.price`, `TrailingAbove.price_offset`, `water_mark` are all `Decimal`).

`NativeTrigger` does not:
- `state` and `next_state` are `google.protobuf.Struct`, whose `Value` number type is a double.
- the `decimal()` CEL function returns `f64` (`alert_engine.rs:31-37`), and on a parse failure logs a warning and **returns 0.0** — a malformed price silently becomes zero inside a comparison.
- `parameters` is `map<string, google.protobuf.Value>` — same double problem.

The trailing-stop example quietly works around this with `'hwm': string(new_hwm)`, so the only statement of the precision contract for stateful triggers is an unexplained `string()` call in a comment.

For a money API this belongs in the proto text, on `NativeTrigger.expression` / `initial_state` / `TriggerResult.next_state`: CEL arithmetic is IEEE-754 double; monetary state must be stored as strings and re-parsed with `decimal()`; `decimal()` yields 0.0 on unparseable input. Better still, make `decimal()` an error rather than 0.0 and document that.

### M2. `Sink` has no destination

`Sink.TelegramNotification` carries `message_template` and nothing else — no `chat_id`, no recipient, no routing key. Every alert on every account goes wherever the server config points.

Any multi-user or multi-channel client is blocked, and adding a *required* destination later is a behavior break for everyone who created alerts without one. Decide now: either add `string chat_id = 2;` (optional, falling back to server default, documented as such), or state in the comment that the destination is server-configured and per-alert routing is out of scope.

Related: the `{{name}}` template language is part of the contract but unspecified. For a `NativeTrigger` the names are the user's own `bindings`, fine. For a `BuiltInTrigger` the binding names are generated internally by `/Users/yuhanzhao/GitHub/ninniku/src/alert/mod.rs` — so a client cannot write a template for a built-in trigger without reading server source. Document the guaranteed names per built-in trigger type (`price`, `threshold`, `water_mark`, …), plus what happens on an unknown name (dropped? left literal?) and how to escape a literal `{{`.

### M3. Two lifecycles for the same object, with no stated precedence

`BotConfig.bot_params` now includes `alert_bot_params`, so an alert can be created two ways:
- `CreateAlert(account_target, alert_definition)` → returns `alert_id`, which the comment says *is* the bot's `bot_id`; and
- `CreateBot(bot_name, account_target, BotConfig{alert_bot_params})` → returns `bot_id`.

Likewise `DeleteBot(bot_id)` will tear down an alert behind `DeleteAlert`'s back, and `UpdateBotConfig` can rewrite an `AlertDefinition` without going through `UpdateAlert`. `UpdateBotStatus` can stop an alert bot, which `GetAlert`/`ListAlerts` (once added) would need to surface.

Nothing in the proto says which path is canonical. Also, `CreateBot` takes a `bot_name` and `CreateAlert` does not — so alerts created via `CreateAlert` presumably get a synthesized name, unstated.

Pick a stance and write it down:
- **Preferred:** document `CreateAlert`/`UpdateAlert`/`DeleteAlert` as the only supported path for alerts, and state that `alert_bot_params` is an internal representation not intended for direct `CreateBot`/`UpdateBotConfig` use; or
- document the alert RPCs as pure sugar over the bot RPCs, and specify the `bot_name` that `CreateAlert` assigns.

Also worth stating on `AlertBotParams`: whether `bot_name` is user-visible for alerts at all, and whether `UpdateBotStatus(STOPPED)` on an alert bot is a supported "pause alert" gesture. If it is, that's a nicer answer than a separate pause RPC — but it needs to be said.

The new `BotMetadata.can_trade` field is good and the comment carries a real invariant ("at most one trading bot per account"). Note it's a `bool` in a place that may later want more than two values (read-only / trade / trade-with-approval); an enum would be more future-proof, but `bool` is defensible.

### M4. `UpdateAlert` is a full replace with unstated state semantics

`UpdateAlertRequest` carries a whole `AlertDefinition` with no `field_mask`. Full-replace is a fine choice for an object this small, but the important question is unanswered: **what happens to trigger state?**

For a trailing stop this is the entire behavior. If a user edits the notification template, does the high-water mark survive, or does the alert re-seed at the current price and effectively reset the stop? Those are very different products, and a client cannot guess.

Add to the comment: whether state is preserved or reset, whether the AlertBot restarts, whether `last_eval_time` resets, and what happens to a trigger whose position in the `triggers` list changed (state is presumably keyed by index — if so, reordering silently swaps state between triggers, which is worth calling out or defending against with a stable per-trigger id).

Consider `bool reset_state = 4;` on the request, or a separate `ResetAlertState` RPC.

### M5. `Alert` is dead, and its comment contradicts `AlertBotParams`

```proto
// Full alert record stored in AlertBotParams. alert_id is server-assigned.
message Alert {
  string          alert_id   = 1;
  AlertDefinition definition = 2;
}
```

`AlertBotParams` stores `AlertDefinition`, not `Alert` (`bot.proto:44-46`). No RPC returns `Alert`, and nothing in `src/` references it. It will be generated into every client as a type that never appears on the wire.

Either give it the read-path job (B2) — which is what it's shaped for — or delete it. Do not ship it as-is; the comment will mislead the first person who reads the file.

### M6. No observability — a broken alert is indistinguishable from a quiet one

There is no `last_evaluated_at`, `last_fired_at`, `fire_count`, or `last_error` anywhere in the surface.

Given B1 (a malformed `fired` key silently means false), B3 (breakouts silently never fire), and M1 (`decimal()` silently returns 0.0), the failure mode of this system is *silence* — and silence is also what a correctly-configured alert that hasn't triggered looks like. A user cannot tell "my alert is working and AAPL just hasn't hit $200" from "my CEL expression has a typo."

Add an `AlertStatus` message alongside the read path:

```proto
message AlertStatus {
  google.protobuf.Timestamp last_evaluated_at = 1;
  google.protobuf.Timestamp last_fired_at     = 2;
  uint64                    fire_count        = 3;
  // Most recent evaluation error (CEL compile/runtime, missing market data).
  // Empty if the last evaluation succeeded.
  string                    last_error        = 4;
}
```

Runtime CEL errors currently surface only as server-side `warn!` logs. That's an operator tool, not an API.

### M7. `required_symbols` is two sources of truth for built-in triggers

```proto
// For BuiltInTrigger, this must include BuiltInTrigger.symbol.
repeated string required_symbols = 4;
```

For `BuiltInTrigger` the symbol is already right there in the message, so this asks the client to restate derivable information and creates a state where the two disagree. The rationale given — "For NativeTrigger, this is the only source of symbol information since CEL expressions are opaque at parse time" — is sound, and applies *only* to `NativeTrigger`.

Cleaner: have the server derive symbols from `BuiltInTrigger.symbol` automatically and document `required_symbols` as *additional* symbols needed by native triggers (consider renaming to `additional_symbols`). If you keep the current shape, at least state that the server rejects a definition whose `required_symbols` omits a built-in trigger's symbol, rather than leaving "must" ambiguous between "validated" and "or else."

### M8. No validation contract anywhere

Proto3 has no `required`, so the comments have to carry it, and they don't. Unspecified today:

- Can `AlertDefinition.eval_schedule` / `sink` be unset? Can `triggers` be empty?
- Can `TriggerConfig.trigger_type`, `Sink.sink_type`, `Baseline.baseline_type`, `BarField.field`, `TrailingAbove.trailing_type` be unset? (Every one of these oneofs has a legal "nothing set" state with no documented behavior.)
- `BuiltInTrigger.baseline` is a plain message field — absent means what?
- **Bounds:** is there a minimum `EvalSchedule.interval`? Nothing stops `{ nanos: 1 }`, and each evaluation of a `NativeTrigger` can call `latest_quote`/`latest_trade`. Max `triggers` per alert? Max `required_symbols`? Max `expression` length? Max `bindings`?
- `BreakoutAbove.lookback_bars` and `multiplier` are `int32` — negative and zero are representable. What do they mean?

Other teams will discover all of this by getting `INVALID_ARGUMENT` in staging. A short "Validation" comment block at the top of `AlertDefinition` listing required fields and numeric bounds costs ten lines and saves a support channel. The interval floor especially is a rate-limit decision you want stated before clients depend on 1-second alerts.

### M9. Percent semantics undefined

`TrailingAbove.percent_offset` / `TrailingBelow.percent_offset` are `Decimal`. Is `"5"` five percent or five hundred percent? The name implies the former, but the whole point of the `Decimal` doc comment added in this branch is that the wire format is an unvalidated string. State it: `// e.g. "5" means 5%.`

Minor consistency note while you're there: `BuiltInTrigger` seeds state via `TrailingAbove.water_mark`, while `NativeTrigger` seeds via `initial_state`. Two mechanisms for one concept. Acceptable — the built-in one is much friendlier — but worth a comment cross-referencing them.

---

## Nits

- **N1. `EvalContext` and `TriggerResult` are schema docs, not wire types, but ship in every client.** `EvalContext` says outright "Never wire-exchanged; provided as documentation and tooling schema" — yet it lands in generated Rust and TypeScript as a real type. Consider splitting the CEL-schema types into `proto/poligun/ninniku/alert/cel_schema.proto` so client codegen doesn't carry phantom types, or at least add a file-header note. (`TriggerResult` is genuinely half-wire — it's the documented shape of the CEL return — so it's more defensible than `EvalContext`.)

- **N2. Implementation names leak into public comments.** `Baseline.high` is documented as "session high via reduce_bars" and `low` likewise. `reduce_bars` is an internal CEL helper (and currently a stub); it means nothing to an API consumer. Describe the semantics, not the mechanism.

- **N3. `NativeTrigger` reads backwards.** "Native" is a near-synonym for "built-in" for most readers, so `BuiltInTrigger` vs `NativeTrigger` is a confusing pair. `CelTrigger` or `ExpressionTrigger` says what it is. Rename is free today, breaking once clients reference the type.

- **N4. `optional` on message fields is a no-op.** `optional google.protobuf.Struct next_state`, `optional Decimal water_mark`, `optional MarketHoursFilter market_hours_filter`, `optional google.protobuf.Struct initial_state` — message fields already have explicit presence in proto3. Harmless and arguably good documentation, but be aware it's inconsistent: `AlertDefinition.sink` and `eval_schedule` have exactly the same presence semantics without the keyword, so a reader shouldn't infer any difference. Either use it everywhere or nowhere.

- **N5. `Empty`-valued oneof arms.** `Baseline`'s `ask`/`bid`/`trade`/`high`/`low` and `BarField`'s six field arms use `google.protobuf.Empty` as tag-only variants. This works and leaves room for each arm to grow fields later, which an enum wouldn't. But the rest of the repo uses enums for closed sets (`TimeUnit`, `BrickColor`, `TrendType`, `AccountStatus`), and `Empty` arms are noticeably more verbose to construct from TypeScript. Defensible either way — just be deliberate, and note that mixing (`bar` carries a payload, the other five don't) is the part that makes it worth a comment.

- **N6. Unqualified `Decimal` reference.** `alert.proto` uses bare `Decimal`, resolved by proto's innermost-outward lookup to `poligun.ninniku.Decimal`. Works, but `marketdata.proto` uses the fully-qualified `.poligun.ninniku.Decimal` form. The relative form is a known footgun — a future `poligun.ninniku.alert.Decimal` would silently rebind every one of these. Prefer the leading-dot form.

- **N7. Import ordering.** `ninniku.proto:9` inserts `alert/alert.proto` after `alpaca/account_info.proto`, breaking the otherwise-alphabetical block. Move it above the `alpaca/` imports.

- **N8. Field alignment style.** The new protos column-align field names and numbers (`google.protobuf.Timestamp now            = 1;`). No other proto in the repo does. Cosmetic, but it will produce noisy diffs on every future field addition since adding a longer name reflows the block.

- **N9. No version in the package path.** `poligun.ninniku.alert`, not `poligun.ninniku.alert.v1`. This matches existing repo convention so it's not a defect, but this branch introduces a brand-new package, which is the cheapest moment you will ever have to establish a versioning path. Worth five minutes of thought given the question is specifically "before other teams build against it."

---

## Unrelated breaking change riding along

`account_info.proto` removes two fields in what is otherwise an alerts PR:

```proto
reserved 7;   // Was pattern_day_trader
reserved 21;  // Was daytrade_count
```

Assessment:
- **Mechanically correct.** Using `reserved` rather than deleting the lines is the right way to retire field numbers, and it prevents accidental reuse.
- **No breakage today.** The checked-in generated client at `/Users/yuhanzhao/GitHub/ninniku/ninniku-fe/src/generated/poligun/ninniku/alpaca/account_info.ts` still declares `patternDayTrader` and `daytradeCount`, but no component under `ninniku-fe/src/components`, `services`, or `misc` references either. Nothing breaks until that file is regenerated, and then only if something starts using them.
- **Two recommendations.** Reserve the *names* too, so they can't be reused with different semantics: `reserved "pattern_day_trader", "daytrade_count";`. And split this into its own commit or PR — an external consumer of `AccountInfo` silently loses two fields, and burying that in an alerts change makes it invisible in review and unfindable in `git log` later.

---

## Rollout gap (not the proto, but blocks the teams you're asking about)

`ninniku-fe`'s codegen script does not include the new package:

```json
"generate:proto": "protoc --proto_path=../protos --ts_out=src/generated ../proto/poligun/ninniku/account/*.proto ../proto/poligun/ninniku/alpaca/*.proto ../proto/poligun/ninniku/bot/*.proto ../proto/poligun/ninniku/marketdata/*.proto ../proto/poligun/ninniku/*.proto"
```

`alert/*.proto` is missing from the glob list. Since `bot.proto` and `ninniku.proto` now import it, protoc will resolve the import for compilation but won't emit `alert.ts` — so the regenerated `bot.ts` and `ninniku.ts` will reference a module that doesn't exist.

Separately, and pre-existing: `--proto_path=../protos` points at a directory that doesn't exist (the directory is `proto`, singular), so imports like `poligun/ninniku/bot/bot.proto` can't resolve and this script cannot currently succeed at all.

The first thing another team does is regenerate clients. Fix both alongside the proto.

---

## Suggested order of work

Before publishing to other teams:

1. Fix the `NativeTrigger.expression` contract and example (B1) — highest blast radius, lowest cost.
2. Change `time_unit` to `marketdata.TimeUnit` (B4) — free now, wire break later.
3. Decide on the non-functional surface: `reserved` or explicit rejection (B3).
4. Resolve `Sink` destination (M2) and `NativeTrigger` rename (N3) — both cheap now, breaking after adoption.
5. Document the state semantics of `UpdateAlert` (M4), validation and bounds (M8), percent units (M9), and the precision contract for CEL state (M1).
6. Either wire up `Alert` via a read path or delete it (M5, B2).

Can follow (purely additive): `ListAlerts`/`GetAlert` (B2) and `AlertStatus` (M6) — but the longer they wait, the more clients will have hardened around the bot-walking workaround.
