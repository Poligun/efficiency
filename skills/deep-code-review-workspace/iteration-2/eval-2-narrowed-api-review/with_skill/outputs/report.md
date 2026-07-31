# Review: cel-alert → origin/HEAD (merge-base `e85ca8d`)

This branch adds a CEL-driven alerting subsystem: a new `poligun.ninniku.alert` package, three RPCs (`CreateAlert`/`UpdateAlert`/`DeleteAlert`), and `AlertBotParams` as a second `BotConfig` variant so each alert runs as its own bot. The *shape* of the contract is good — the `BuiltInTrigger`/`NativeTrigger` split is the right seam, `TriggerConfig` as a thin oneof wrapper will age well, and `EvalContext` as a documentation-only message is a genuinely nice touch. The problem is **honesty**. This contract describes a working alerting system; behind it, notifications are never delivered, five of the six built-in trigger shapes can never fire, `DeleteAlert` fails on every alert it is given, `UpdateAlert` returns UNIMPLEMENTED, and three fields the caller is invited to set are read by nothing. Nine separate promises in this proto are contradicted only by the implementation — and the author *did* disclose one gap correctly (`MarketHoursFilter.pre_market`, "Not yet implemented"), which proves the idiom was available and makes the silence everywhere else read as deliberate.

**If other teams start building against this proto as written, essentially everything they code will compile and almost nothing will work.** That is the headline. Most of the fixes are one-line comments; a few are real decisions. Nothing here argues against the design.

**Coverage.** Wire/API contracts only — the five protos plus `build.rs`, which the scope script correctly routed into this aspect. I **skipped `code_api`, `logic`, and `convention` at your request** ("skip the implementation"). Worth knowing: the scope detector rated all three `active` at `strength: strong` (1,215 changed source lines across `src/alert/`, `src/bot/`, `src/server/`), so that is real unreviewed surface, not an absence of things to find. I read the implementation freely to test whether the contract is honest — that is where most of what follows comes from — but every finding is anchored at the proto or `build.rs` line that makes the promise, and I have not reported implementation defects you didn't ask about.

Two disclosures about the run itself:

- **Verification is partial.** One wire-contract reviewer ran independently at `opus`, and five verifiers at `sonnet`. All five verdicts came back **GROUNDED**, and two of them materially changed the report (see F11 and F13). Twelve findings are at MEDIUM or above, so under the normal budget all twelve would have been checked; I verified five and stamped the rest `unverified`. Findings marked *corroborated* were reached independently by me and by the wire-contract agent, which is evidence they are real but is **not** a substitute for verification. A ~40-minute harness outage early in the session cost the budget that would have covered the rest.
- **Slightly over the length guideline** — 17 findings against a soft cap of 15. I merged three and demoted two to design notes rather than cut anything; the honesty cluster is genuinely nine distinct contract promises, each with its own anchor and its own one-line fix, and collapsing them would hide which ones to fix.

---

## Needs a decision before merge

### D1 — `Decimal`'s new doc disclaims validation while the parser substitutes `0.0` (CRITICAL · needs-decision · GROUNDED)
`proto/poligun/ninniku/well_known_types.proto:5` · verified

This comment is new in this branch, and this branch is also the first consumer to violate both halves of it. Every `Decimal` on the alert path is parsed to `f64` — so "without losing precision" stops being true exactly where prices are compared — and because the contract explicitly declines to validate, a malformed value becomes `0.0` rather than an error. The result is not a rejected request but an **inverted decision**: `RiseAbove{price: "$12.50"}` becomes `price >= 0`, which fires on the first tick and every tick after; `FallBelow` with the same typo becomes `price <= 0` and can never fire. The client is told `CreateAlert` succeeded either way.

```proto
// Decimal is a wrapper around string to represent decimal numbers without losing precision.
// This is used for all price and quantity fields in the API.
// The value should be a string representation of a decimal number, e.g. "123.45". The API will not perform any
// validation on the format of the string, so it is the responsibility of the client to ensure that it is a valid
// decimal number.
```

`src/alert/alert_engine.rs:31` — `ctx.add_function("decimal", |s: Arc<String>| -> f64 { s.parse::<f64>().unwrap_or_else(|_| { warn!(…); 0.0 }) })`. `src/server/mod.rs:682-701` — `validate_alert_definition` checks only that `triggers` is non-empty, `interval` is present and `sink` is present.

The verifier found the detail that makes this cheap to fix: **`src/server/proto.rs:51-59` already implements `TryFrom<Decimal> for bigdecimal::BigDecimal`, which parses properly and returns an `Err`** — and nothing on the alert path calls it. The primitive exists; it just isn't wired in.

**Open question.** Is the no-validation clause an intentional API guarantee, or a description of today's implementation? If intentional, `CreateAlert` must reject unparseable `Decimal`s at admission and the disclaimer should be narrowed to storage. If descriptive, the comment shouldn't ship as a promise at all. Either way, `0.0` is the wrong sentinel for an unparseable price — `NaN` fails closed, `0.0` fails open.

### D2 — Triggers carry per-trigger state but have no identity (HIGH · needs-decision · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:226`

The contract promises each trigger keeps independent state across evaluations, and offers `UpdateAlert` to replace the whole `AlertDefinition`. But `TriggerConfig` has no identifier, so state can only be keyed by list position — and it is. Delete or reorder a trigger and the survivors inherit another trigger's high-water mark: a trailing-stop alert fires against a water mark it never observed. This is reachable today even though `UpdateAlert` is stubbed (F4), because `UpdateBotConfig` accepts the same `BotConfig` and swaps it under a live `AlertBot`.

```proto
  // One or more triggers evaluated on each tick. The alert fires (dispatches
  // to sink) when any trigger returns TriggerResult{fired: true}.
  // Each trigger maintains independent state across evaluations.
  repeated TriggerConfig triggers = 1;
```

`src/bot/alert_bot.rs:12` — `/// Per-trigger CEL state, indexed by trigger position in AlertDefinition.triggers`. `src/bot/alert_bot.rs:62-65` — the state vector is grown, never re-keyed or cleared. `src/bot/bot_loop.rs:55-59` — `BotEvent::ConfigUpdate` calls `context.update_bot_config(bot_config)` while the `AlertBot` object, and its `trigger_states`, survive untouched.

**Open question.** Should `TriggerConfig` carry a `trigger_id` that state is keyed by? Adding it later is wire-additive, so this isn't a migration trap — but every alert created before it exists carries the bug, and no backfill can recover which state belonged to which trigger.

### D3 — The alert resource has no read operation, and its id is welded to `bot_id` (HIGH · needs-decision · unverified)
`proto/poligun/ninniku/ninniku.proto:226`

`CreateAlert`/`UpdateAlert`/`DeleteAlert` exist; `GetAlert` and `ListAlerts` do not. A client that loses an `alert_id` cannot recover it through the alert API — the only path is `GetBotMetadata`/`GetBotStatuses`, then unwrapping `BotMetadata → BotConfig → AlertBotParams → AlertDefinition`. That works *only* because of the sentence below, which promotes an implementation detail into the wire contract.

```proto
message CreateAlertResponse {
  // Server-assigned alert ID. Also used as the underlying AlertBot's bot_id.
  string alert_id = 1;
}
```

The missing read operation has a fingerprint: `Alert { alert_id, definition }` at `alert.proto:242` is defined, documented as *"Full alert record stored in AlertBotParams"* — which `bot.proto:45` contradicts, since `AlertBotParams` holds a bare `AlertDefinition` with no `alert_id` — and is referenced by no RPC, no message, and no code in `src/` or the frontend. It reads exactly like the response payload for a `GetAlert` that was designed and then dropped.

**Open question.** Is an alert a first-class resource with its own read/list surface, or permanently a projection of the bot API? That one answer settles three things: whether `alert_id` may ever diverge from `bot_id`, whether the orphaned `Alert` message gets an RPC or gets deleted, and whether other teams should be told to read alerts through the bot API. Decoupling the ids after clients rely on the documented equality *is* a breaking change.

---

## Findings

### F1 — Sink delivery is the contract's headline promise and never happens (CRITICAL · scoped · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:223`

The contract defines an alert by what it does on firing, and `CreateAlert` *rejects* a definition with no sink. Nothing is ever delivered: the notification is formatted and written to a log line behind a TODO. Every alert another team builds against this contract will be accepted, will run, will evaluate correctly, and will notify nobody.

```proto
  // One or more triggers evaluated on each tick. The alert fires (dispatches
  // to sink) when any trigger returns TriggerResult{fired: true}.
```

`src/bot/alert_bot.rs:105-107`:
```rust
            // TODO: deliver via Telegram when Sink support is wired up
            info!("AlertBot: trigger {} fired — {}", i, message);
            warn!("AlertBot: Telegram notification not yet implemented");
```

`src/server/mod.rs:697` makes the sink mandatory: `if def.sink.is_none() { return Err(Status::invalid_argument("alert_definition.sink is required")); }`.

The same message carries a second unimplemented promise: `alert.proto:210` documents `{{name}}` binding substitution in `message_template`, and `alert_bot.rs:99` uses the template verbatim (`SinkType::Telegram(t) => t.message_template.clone()`). A client writing `"AAPL ask {{price}} crossed above {{threshold}}"` gets literal braces. That half is latent behind this one, and ships broken the moment delivery lands.

**Fix.** Say so in the contract, the way `MarketHoursFilter` already does — `// Not yet delivered; firings are logged only.` on `Sink` is one line and converts a silent gap into a known one. Or reject `CreateAlert` with UNIMPLEMENTED until delivery exists.

### F2 — Five of the six built-in trigger shapes can never fire (CRITICAL · scoped · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:87`

`Baseline.high`, `Baseline.low`, `Baseline.bar`, `BreakoutAbove` and `BreakoutBelow` all resolve through one CEL function, `reduce_bars`, which is a stub returning `NaN` — and every IEEE-754 comparison against `NaN` is false, so these triggers evaluate successfully and never fire, in either direction. The contract describes each as working, in the indicative, with no hedge.

```proto
      google.protobuf.Empty high  = 4; // session high via reduce_bars
      google.protobuf.Empty low   = 5; // session low via reduce_bars
…
  // Fires when the baseline price exceeds the highest high of the last
  // lookback_bars completed bars.
  message BreakoutAbove {
```

`src/alert/alert_engine.rs:98-116` — *"reduce_bars: stub — bar range queries not yet in MarketData trait. Returns sentinel values so breakout triggers silently never fire"* … `f64::NAN`. This is not a passing TODO: `src/bot/market_data.rs:6-24` shows the `MarketData` trait has `latest_bar`, `latest_quote`, `latest_trades` and no range query at all, so the capability genuinely does not exist yet.

**Fix.** Annotate these five options in the proto as not yet implemented, or reject them at `CreateAlert` with UNIMPLEMENTED. A price alert that silently never fires is the worst failure mode this feature has — the user finds out from the trade they missed.

### F3 — `DeleteAlert` is documented as unconditional and fails on every alert (CRITICAL · scoped · GROUNDED)
`proto/poligun/ninniku/ninniku.proto:61` · verified

`CreateAlert` starts the bot immediately, so an alert's steady state is Running. `DeleteAlert` goes straight to `delete_bot`, which refuses to delete a running bot, and never sends a stop first. The documented "unconditionally" therefore never applies: `DeleteAlert` returns `Internal: Cannot delete a running bot`, and the only escape is for the client to drop out of the alert API into the *bot* API and call `UpdateBotStatus(STOPPED)` first — which the alert contract never mentions.

```proto
  // Alert management
  // Each alert runs in its own AlertBot. CreateAlert creates (and starts) the
  // AlertBot; DeleteAlert stops and removes it unconditionally.
```

`src/server/mod.rs:624-627` — `CreateAlert` calls `start_bot`. `src/bot/bot_manager.rs:191-193` — `if metadata.status == BotStatus::Running as i32 { return Err(…"Cannot delete a running bot"…) }`. `src/server/mod.rs:664-667` — `delete_alert` calls `delete_bot` with no preceding stop.

One precision the verifier added: the `Running` status is written asynchronously via the ack channel, so a strict reading is "fails for any client that can't beat the ack" rather than "always fails". The ack is sent as the first line of the spawned loop (`src/bot/bot_loop.rs:15-16`), before any evaluation, so no real gRPC client wins that race.

**Fix.** Have `DeleteAlert` stop the bot and await the `Stopped` ack before deleting, or drop "unconditionally" and document the required stop-then-delete sequence. The word is load-bearing — it's what tells a client they don't need a two-step teardown.

### F4 — `UpdateAlert` is documented as working and returns UNIMPLEMENTED (HIGH · mechanical · unverified, corroborated)
`proto/poligun/ninniku/ninniku.proto:66`

The RPC is published on the service with a comment describing what it does and no caveat, next to two RPCs that are implemented. The handler is one line. A team that builds an alert-editing screen against this discovers at runtime that the only way to change an alert is delete-and-recreate — which mints a new `alert_id` and discards accumulated trigger state.

```proto
  // Replace the AlertDefinition of an existing alert.
  rpc UpdateAlert (UpdateAlertRequest) returns (UpdateAlertResponse);
```

`src/server/mod.rs:636` — `Err(Status::unimplemented("UpdateAlert not yet implemented"))`.

**Fix.** Append `Not yet implemented.` to the comment. One line, and it's the cheapest item in this report.

### F5 — The contract's one worked example cannot be evaluated (HIGH · mechanical · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:42`

`NativeTrigger.expression` is the extension point of the whole feature, and this example is the thing every other team will copy. It shows protobuf message-construction syntax returning `TriggerResult`; the evaluator requires a plain CEL map with string keys and registers no `TriggerResult` type in the CEL context. The example also stores `next_state` as a *string*, which would break the following evaluation even if the outer form were accepted, because `max_decimal`/`min_decimal` take floats.

```proto
  // CEL expression returning TriggerResult. May reference any binding by name.
  // Example (trailing stop):
  //   TriggerResult{
  //     fired: price <= new_hwm - decimal('1.00'),
  //     next_state: {'hwm': string(new_hwm)}
  //   }
```

`src/alert/alert_engine.rs:263-272` — `parse_trigger_result` requires `Value::Map` and reads the literal keys `fired`, `message`, `next_state`. `src/alert/mod.rs:13-14` states the true protocol and contradicts the proto directly: *"The resulting trigger's `expression` returns a CEL map `{'fired': bool, 'next_state': map}`. State values are stored as floats (not strings)."*

**Fix.** Correct the example to the map form and drop the `string(…)` wrapper: `next_state: {'hwm': new_hwm}`. The header at `alert.proto:12` ("TriggerResult — returned by every NativeTrigger CEL expression") needs the same treatment — `TriggerResult` is the *decoded* result, not what the expression returns.

### F6 — `time_unit` is a free string where the repo already has a `TimeUnit` enum (HIGH · mechanical · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:94`

Three new fields model bar granularity as free text in a schema that already ships `poligun.ninniku.marketdata.TimeUnit` and already uses it for exactly this in `GetBarsRequest` and `Bars`. The consequence isn't cosmetic: the resolver maps anything unrecognised to 60 seconds, so a client sending `"DAY"` for a 20-bar breakout gets a **20-minute** lookback instead of 20 days, with no error. `"HOUR"` is accepted here despite not existing in the enum at all.

```proto
      int32  multiplier = 1;
      string time_unit  = 2; // e.g. "MINUTE"
```

`proto/poligun/ninniku/marketdata/marketdata.proto:13-16` — `enum TimeUnit { TIME_UNIT_UNKNOWN = 0; TIME_UNIT_MINUTE = 1; }`. `proto/poligun/ninniku/ninniku.proto:85` — `poligun.ninniku.marketdata.TimeUnit time_unit = 3;`, the existing convention. `src/alert/mod.rs:207-211` — `"MINUTE" => 60, "HOUR" => 3600, _ => 60`.

**Fix.** Use the existing enum. If it's too narrow — it only has `MINUTE` — extend the enum, which is additive. Converting `string` to `enum` on the same field number after release is wire-breaking, so this is free now and expensive later.

### F7 — `NativeTrigger.initial_state` is accepted, stored, and never read (HIGH · scoped · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:53`

The field promises a specific, checkable effect: seed state visible as `context.state["key"]` on the first evaluation. `AlertBot` initialises every trigger's state to `None`, the engine turns absent state into an empty map, and a repo-wide grep for `initial_state` returns exactly one hit — the translator writing `None`. A native trailing stop seeded with a known entry price, which is the documented use case, sees `{}` on its first tick and either errors out or takes the wrong branch.

```proto
  // Seed state for the very first evaluation, accessible as context.state["key"].
  // On subsequent evaluations, TriggerResult.next_state takes precedence.
  optional google.protobuf.Struct initial_state = 4;
```

`grep -rn "initial_state" src/` → only `src/alert/mod.rs:160` (`initial_state: None`). `src/bot/alert_bot.rs:21` — `trigger_states: Mutex::new(vec![None; trigger_count])`. `src/alert/alert_engine.rs:218-220` — absent state becomes an empty map.

**Fix.** Worth wiring rather than documenting away: seed `trigger_states[i]` from `initial_state` when it is `None`. It's the mechanism that gives native triggers the equivalent of `TrailingBelow.water_mark`.

### F8 — `required_symbols` promises a subscription that nothing performs (HIGH · scoped · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:238`

The comment makes three claims — the engine subscribes to these symbols, `BuiltInTrigger.symbol` must be among them, and for `NativeTrigger` this is the *only* source of symbol information — and nothing implements or enforces any of them. `grep -rn "required_symbols" src/` returns zero hits.

```proto
  // Symbols required across all triggers. The engine subscribes to market
  // data for these symbols once for the whole alert.
  // For BuiltInTrigger, this must include BuiltInTrigger.symbol.
  // For NativeTrigger, this is the only source of symbol information since
  // CEL expressions are opaque at parse time.
  repeated string required_symbols = 4;
```

The downstream consequence is worse than dead weight. An alert on an unsubscribed symbol gets `Ok(None)` from `latest_quote`, which `src/alert/alert_engine.rs:63-66` converts to an `ExecutionError`, which `alert_engine.rs:180` propagates out of `evaluate_alert_definition` — aborting every remaining trigger in the alert, not just the one that couldn't resolve. The bot then retries on its interval forever while the client holds an `alert_id` it believes is live.

**Fix.** Wire it (subscribe at `CreateAlert`, enforce the containment rule) or delete the field and the paragraph. Leaving it is the worst option, because the comment is specific enough to be designed against.

### F9 — `regular_hours` is unread, and its siblings' disclosure implies it works (HIGH · scoped · unverified, corroborated)
`proto/poligun/ninniku/alert/alert.proto:193`

Marking two of three fields "not yet implemented" is a deliberate-looking signal that the third one is. It isn't — `grep` finds no reference to `market_hours_filter`, `regular_hours`, or any session-window logic in `src/`, and `AlertBot` reads only `eval_schedule.interval`. An equity alert configured with `regular_hours: true` evaluates around the clock against whatever quote is cached, so it can fire at 03:00 on a price that hasn't moved since the close.

```proto
// Controls which market session windows are active for evaluation.
// pre_market and post_market are reserved for future implementation.
message MarketHoursFilter {
  bool regular_hours = 1;

  // Not yet implemented.
  bool pre_market  = 2;
  bool post_market = 3;
}
```

Compounding it, `alert.proto:186` says *"If absent, the alert always evaluates"* — which tells the reader that **presence** restricts evaluation. It doesn't.

**Fix.** Extend the "Not yet implemented" note to the whole message until the session filter exists. This is the one place the author used the right idiom, and it's doing the opposite of its job by being applied to only part of the message.

### F10 — `percent_offset` has no documented unit and both readings fail silently (MEDIUM · mechanical · unverified)
`proto/poligun/ninniku/alert/alert.proto:130`

The implementation treats the value as a fraction — `0.05` means 5% — but the field is named `percent_offset` and the `Decimal` doc's own example is `"123.45"`, so "5" for 5% is the natural reading. It yields a `TrailingBelow` threshold of `hwm * (1 - 5)`, a negative price the alert can never fall below, and a `TrailingAbove` threshold of `lwm * 6`. Both never fire, with no error and no log.

```proto
  message TrailingAbove {
    oneof trailing_type {
      Decimal price_offset   = 1;
      Decimal percent_offset = 2;
    }
```

`src/alert/mod.rs:89-92` — `format!("new_lwm * (decimal('1') + decimal('{}'))", d.value)`; `src/alert/mod.rs:54-57` — `format!("new_hwm * (decimal('1') - decimal('{}'))", d.value)`.

**Fix.** Document the unit on both `TrailingAbove` and `TrailingBelow`: `// Fraction, not percent: 0.05 means 5%.` Renaming to `fraction_offset` is cleaner and still free, before anyone has generated a client.

### F11 — `symbol` and `time_unit` are pasted unescaped into generated CEL source (MEDIUM · scoped · GROUNDED)
`proto/poligun/ninniku/alert/alert.proto:80` · verified

`BuiltInTrigger.symbol` and `time_unit` are interpolated into CEL program text via `format!` with no escaping and no documented charset, and the contract explicitly declines to validate them. A symbol containing an apostrophe produces a malformed program that fails `Program::compile`.

```proto
message BuiltInTrigger {
  string symbol = 1;
```

`src/alert/mod.rs:168` — `format!("latest_quote('{}').ask", symbol)`. `src/alert/mod.rs:182-184` — the same pattern for `reduce_bars`.

**I want to be precise about what this is not.** The wire-contract agent filed this as a CRITICAL injection vulnerability. It isn't one, and the verifier confirmed the reasoning: `NativeTrigger.expression` already lets any caller submit arbitrary CEL through the same `evaluate_native_trigger` with the same function table (`src/alert/alert_engine.rs:159-162`), and there is no auth interceptor (`src/main.rs:117-124`) that would make one path more privileged than the other. Injecting CEL via `symbol` grants a caller nothing they don't already have by sending a `NativeTrigger`. **No privilege boundary is crossed.**

What survives is a correctness and observability defect. The compile failure is swallowed at `src/bot/alert_bot.rs:79-83` — `error!(…); return Ok(interval)` — so the alert reports success at creation, fails on every evaluation cycle forever, and the client never learns.

**Fix.** Document a charset constraint on `symbol`, and validate it at `CreateAlert` so a bad symbol is rejected at admission rather than failing invisibly on every tick.

### F12 — `EvalSchedule.interval` has no documented minimum; one nanosecond spins the loop (MEDIUM · scoped · GROUNDED)
`proto/poligun/ninniku/alert/alert.proto:184` · verified

The field documents units by example but states no lower bound, and validation only checks presence. `bot_loop` rejects non-positive durations, so `{seconds: 0}` is caught — but `{seconds: 0, nanos: 1}` is positive, passes the guard, and becomes the sleep duration, re-invoking evaluation against Redis-backed `latest_quote` essentially continuously.

```proto
  // How frequently to evaluate all triggers. E.g. { seconds: 5 }.
  google.protobuf.Duration interval = 1;
```

`src/server/mod.rs:692` — presence-only check. `src/bot/alert_bot.rs:54-58` — converted with no clamp. `src/bot/bot_loop.rs:40` — `Ok(duration) if duration <= chrono::Duration::zero()`, which 1ns passes. The sibling bot type does clamp: `src/bot/bot.rs:98` — `chrono::Duration::seconds(max(1, params.interval_seconds))`, which the verifier confirmed via `git blame` predates this branch. The alert path is the outlier against an existing in-repo convention.

**Fix.** State a minimum in the contract and enforce it at `CreateAlert`. `NoOpBotParams` shows the house style.

### F13 — The new `alert/` package falls outside the frontend's codegen glob (MEDIUM · scoped · GROUNDED) · **latent** behind a pre-existing codegen break
`proto/poligun/ninniku/bot/bot.proto:6` · verified

This import puts `alert/alert.proto` into the import graph of both `bot.proto` and `ninniku.proto`, which the TypeScript frontend generates its client from. The `generate:proto` script enumerates `account/`, `alpaca/`, `bot/`, `marketdata/` and the top level — but not `alert/` — and `@protobuf-ts` does not emit non-requested files transitively (`generateDependencies: false`; the plugin filters to `request.fileToGenerate` plus well-known types). So a regenerated `bot.ts` would import `AlertDefinition` from a file that was never written.

```proto
import "poligun/ninniku/account/account.proto";
import "poligun/ninniku/alert/alert.proto";
```

`ninniku-fe/package.json:7` — the glob list, with no `alert/*.proto`.

**The verifier corrected the consequence I and the wire agent both had wrong, and the correction matters.** I was going to tell you the frontend cannot build against this branch. It can't build *today either*: `--proto_path=../protos` (plural) points at a directory that doesn't exist — the tree has `proto/` — and `git show e85ca8d9:ninniku-fe/package.json` is byte-identical, so that break predates this branch entirely. `ninniku-fe/src/generated` is also gitignored, so there's no stale checked-in client. The honest statement is: **this branch adds a second, latent break that will surface for whoever fixes the first one.** Given your question is specifically about other teams building against this proto, it's worth fixing at the same time.

**Fix.** Add `../proto/poligun/ninniku/alert/*.proto` to the glob. (The `protos`/`proto` path bug is pre-existing and not this branch's to fix, but it's why nobody has noticed.)

### F14 — `AccountInfo` drops two PDT fields inside an alerting branch (MEDIUM · needs-decision · unverified, corroborated)
`proto/poligun/ninniku/alpaca/account_info.proto:31`

The `reserved` ritual is correct — that is not the finding, and reporting it as one would penalise the author for doing the right thing. The finding is *what* was removed and *where*. `pattern_day_trader` and `daytrade_count` tell a client whether an account is under a pattern-day-trader restriction and how many day trades it has used, and they are being removed in a branch about CEL alerting, with no mention in any commit message.

```proto
  reserved 7; // Was pattern_day_trader
…
  reserved 21; // Was daytrade_count
```

**Blast radius, stated honestly.** I grepped the whole tree (`.rs`, `.proto`, `.ts`, `.py`, `.json`). The only in-repo reader was the conversion in `src/alpaca/trade_api/account_info.rs`, deleted in the same change. The only other hits are in `ninniku-fe/src/generated/…/account_info.ts`, which is **gitignored build output**, not a committed client — and no hand-written frontend code reads `patternDayTrader` or `daytradeCount`. So nothing in this repo notices. I cannot see other repos or any deployed client bundle. I'm keeping this at MEDIUM rather than HIGH precisely because I could not find a live consumer; if one exists outside this repo, a client compiled against the old descriptor will render "not a pattern day trader, 0 day trades used" for an account that is flagged and at its limit, and that would be CRITICAL.

**Open question.** Is dropping PDT status intentional and permanent, or incidental cleanup? If intentional it belongs in its own change with a note for out-of-repo clients. If the data is still wanted, these are the last two field numbers that can be reclaimed cheaply.

---

## Design notes

Opinions, unranked, explicitly not defects.

- **`build.rs` silently drops serde from the whole bot package.** The branch deletes the `.type_attribute(".poligun.ninniku.bot", "#[derive(serde::Serialize, serde::Deserialize)]")` block while the `.poligun.ninniku.account` block stays. This is a *forced* consequence, not a free choice: `bot.proto:45` embeds `AlertDefinition`, which transitively contains `google.protobuf.Struct`/`Value`, and `prost-types` ships no serde impls — so the derive could not compile. I found no in-repo consumer (bot metadata persists via `prost::encode` + base64 at `src/bot/bot_metadata.rs:74-85`), so the cost today is an undocumented capability asymmetry between two sibling packages rather than a break. Worth a one-line comment in `build.rs` saying why, so the next person doesn't "restore" it.
- **`BotMetadata.can_trade` goes stale on reconfigure.** It's documented as fact on the wire, but `bot_manager.rs:113-118` deliberately re-derives it rather than trusting the stored value, and `bot_manager.rs:166-169` copies the old value forward with struct-update syntax — so switching a bot between `AlertBotParams` and `NoOpBotParams` leaves the field permanently wrong. Either recompute it in `update_bot_config`, or document it as derived-from-`bot_config` and never read it server-side. The two call sites currently disagree about which it is.
- **`MarketHoursFilter` with all three bools false** is representable and undocumented — presumably "never evaluate", which is indistinguishable from a client that forgot to set anything. `EvalSchedule` already distinguishes absent from present, so all-false is the only ambiguous state.
- **`BuiltInTrigger.baseline` and the `trigger_type`/`baseline_type`/`field` oneofs are all effectively required** — the translator errors on each when unset — but nothing in the contract says so. proto3 has no `required`, so a comment is the only mechanism available.
- **`EvalContext` doesn't say what `last_eval_time` holds on the first evaluation.** The engine substitutes `now` (`alert_engine.rs:210-212`), making any `last_eval_time..now` window zero-width on the first tick — which silently affects the `Baseline.high`/`low` expressions that use exactly that range.

## Could not resolve

- **Whether anything outside this repo reads `AccountInfo.pattern_day_trader` / `daytrade_count`.** F14's severity turns entirely on this. What would settle it: a grep for those field names across the client repos and any deployed-SDK directories, or a look at whether the gRPC service is exposed beyond `ninniku-fe`.
- **Whether the honesty gaps (F1, F2, F4, F7, F8, F9) are known-and-deferred or unnoticed.** Every one is a contract describing behavior the implementation doesn't provide, and the branch discloses exactly one such gap correctly. If they're all known, most fixes are a comment and this report is a checklist. If they aren't, the ordering above is roughly the order I'd fix them in. What would settle it: your answer, or a design doc for the feature.
