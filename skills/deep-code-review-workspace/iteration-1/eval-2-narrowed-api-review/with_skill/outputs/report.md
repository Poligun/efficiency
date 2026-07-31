# Review: cel-alert → origin/HEAD (proto / API design only)

This branch adds a user-defined alerting API: a new `poligun.ninniku.alert` package, three RPCs
(`CreateAlert`/`UpdateAlert`/`DeleteAlert`), and `AlertBotParams` bolted into the existing
`BotConfig` oneof so each alert runs as a bot. The shape is mostly good — the
`BuiltInTrigger`/`NativeTrigger` split is the right decomposition, `Decimal` is used for money
rather than a float, and the oneofs are extensible. **The problem is not the shape, it's the
honesty:** seven documented behaviors in `alert.proto` have no implementation behind them, and the
proto discloses exactly one of them (`pre_market`/`post_market`). That selective disclosure is
worse than no disclosure, because it teaches a reader that unmarked fields *are* implemented.
Another team building against this file today would build against four promises that silently do
nothing and one worked example that doesn't compile.

**Coverage.** Only the **wire-contract aspect** ran, at your request. Scope detection rated all
four aspects `strong` (1215 changed source lines, 3 new modules, a new directory); I skipped
**code_api** (`src/alert/*`, `src/bot/alert_bot.rs`, `src/server/proto.rs` — Rust surface design),
**business logic** (all 18 source files), and **conventions** (the new `src/alert/` module vs. repo
patterns) because you asked to skip the implementation. `src/` was read as *evidence only* — to
check whether a declared contract surface has a reader — so implementation defects that don't
contradict the proto are not reported here. I did include `build.rs` in scope, since it is the
codegen contract for these protos; say the word if you want it out.

One agent found 12 candidates; 12 verifiers ran (no cap hit); one round-2 tracer answered a gap I
found during arbitration and correctly returned no finding. Two candidates were demoted to design
notes. I overrode two verifier severity proposals, disclosed inline. Nothing was posted to GitHub;
this is a terminal report only.

---

## Needs a decision before merge

### F8 — Client strings are interpolated verbatim into executable CEL source (HIGH · needs-decision · grounded)
`proto/poligun/ninniku/well_known_types.proto:7`

`BuiltInTrigger.symbol` and every `Decimal.value` in a built-in trigger are string-formatted
directly into the CEL program text the server then compiles and runs, and this branch adds a doc
comment to `Decimal` that *promises* no validation will happen. `validate_alert_definition`
(`src/server/mod.rs:682-701`) checks only that `triggers`, `eval_schedule`, and `sink` are present —
it never inspects these strings. A caller sending `price.value = "0') || true || decimal('0"`, or a
symbol containing a quote, gets that text compiled as CEL by the server: at minimum an alert that
always fires, and it costs nothing to write.

```
proto/poligun/ninniku/well_known_types.proto:7
// The value should be a string representation of a decimal number, e.g. "123.45". The API will not perform any
// validation on the format of the string, so it is the responsibility of the client to ensure that it is a valid
// decimal number.

src/alert/mod.rs:32
let expr = format!("{{'fired': price >= decimal('{}')}}", price.value);
```

**Open question.** Do you constrain these in the contract — document a symbol charset and a
`Decimal` grammar, and reject violations at `CreateAlert` — or stop building CEL by concatenation
and bind values as CEL variables instead? The second is the robust fix but changes the translator.
The first is a contract commitment you can loosen but never tighten, which is why it needs deciding
before other teams read this file.

*Severity note: the verifier proposed MEDIUM, on the grounds that the CEL function registry is
fixed and safe (`decimal`, `latest_quote`, `latest_trade`, `reduce_bars` — no exec primitives), the
notification sink is currently inert, and `main.rs:106` binds to loopback with no auth interceptor
found. Those are all true, and all temporary states of an in-progress feature. I kept HIGH because
the finding you're being asked to rule on is the **contract shape** — a documented no-validation
guarantee on a field that reaches a compiler — and that is exactly the thing that gets expensive
after other teams build on it.*

---

## Findings

### F1 — UpdateAlert is fully specified and always returns UNIMPLEMENTED (CRITICAL · scoped · grounded)
`proto/poligun/ninniku/ninniku.proto:67`

The contract documents `UpdateAlert` as "Replace the AlertDefinition of an existing alert" with no
caveat, gives it a fully-populated request message, and `AlertDefinition`'s own comment says it is
"Used in CreateAlert / UpdateAlert". The handler is a one-line stub. A client that builds an
alert-editing flow against this contract compiles, ships, and gets `UNIMPLEMENTED` at runtime; the
only workaround is `DeleteAlert` + `CreateAlert`, which mints a fresh `bot_id` and therefore
discards the alert_id every client has stored plus all accumulated trigger state.

```
proto/poligun/ninniku/ninniku.proto:66-67
  // Replace the AlertDefinition of an existing alert.
  rpc UpdateAlert (UpdateAlertRequest) returns (UpdateAlertResponse);

src/server/mod.rs:636
  Err(Status::unimplemented("UpdateAlert not yet implemented"))
```

**Fix.** Either implement it, or say so in the proto — `// Not yet implemented.` on line 66, the
same disclosure this file already gives `pre_market`. Do not ship the RPC undisclosed.

### F2 — Sink promises Telegram delivery and `{{name}}` templating; neither exists (CRITICAL · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:213`

`Sink.TelegramNotification` carries no "not yet implemented" note, and both `AlertDefinition` and
`AlertBotParams` state that a firing alert "dispatches to sink". The bot logs the message and warns
that Telegram isn't wired up; the documented `{{name}}` binding substitution doesn't exist anywhere
in the tree — `message_template` is `.clone()`d verbatim and used once. A client creates a price
alert, the trigger fires correctly, and nobody is ever notified, with no API-visible signal that
delivery failed. This is the whole point of the feature.

```
proto/poligun/ninniku/alert/alert.proto:210-213
    // Notification text. Binding names from the trigger are substituted as
    // {{name}}. E.g. "AAPL ask {{price}} crossed above {{threshold}}"
    // TriggerResult.message overrides this template when set.
    string message_template = 1;

src/bot/alert_bot.rs:105-107
  // TODO: deliver via Telegram when Sink support is wired up
  warn!("AlertBot: Telegram notification not yet implemented");
```

**Fix.** Mark `TelegramNotification` and the `{{name}}` substitution as not-yet-implemented in the
proto, or implement them. Given that F1–F7 are all the same defect, consider one convention: every
field in this file that isn't backed yet gets the `// Not yet implemented.` line, applied
exhaustively rather than to two fields.

### F3 — The `NativeTrigger.expression` example in the proto cannot compile (HIGH · mechanical · grounded)
`proto/poligun/ninniku/alert/alert.proto:46`

`expression` is documented as "CEL expression returning TriggerResult" and the worked example uses
CEL message-construction syntax, `TriggerResult{...}`. No `TriggerResult` type is ever registered
with the CEL context — `alert_engine.rs` only calls `add_variable_from_value`/`add_function` — and
the evaluator hard-requires a `Value::Map`. Your own built-in translator emits map literals
(`{'fired': ..., 'next_state': ...}`), which is the real protocol. Note that `EvalContext` in this
same file *does* carry the caveat "Never wire-exchanged; provided as documentation and tooling
schema" — `TriggerResult` carries none, so it reads as a real wire type. A client who copies the
example verbatim gets a CEL failure that is logged server-side only; `CreateAlert` already returned
OK, so the alert looks healthy and silently never fires.

```
proto/poligun/ninniku/alert/alert.proto:40-45
  // CEL expression returning TriggerResult. May reference any binding by name.
  // Example (trailing stop):
  //   TriggerResult{
  //     fired: price <= new_hwm - decimal('1.00'),
  //     next_state: {'hwm': string(new_hwm)}
  //   }

src/alert/alert_engine.rs:264-268
  let map = match value { Value::Map(ref m) => m,
      _ => return Err(format!("Expression must return a map with 'fired' key, got: {:?}", value)) };
```

**Fix.** Rewrite the comment to the map form and add the same "documentation only" caveat
`EvalContext` has. Also fix `string(new_hwm)` in the example — `src/alert/mod.rs:14` says state
values are stored as floats, and the translator emits `'hwm': new_hwm` unwrapped.

### F4 — Two of six trigger types and three of six baselines can never fire (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:151`

`BreakoutAbove`, `BreakoutBelow`, and the `high`, `low`, and `bar` baselines all translate to a
`reduce_bars` CEL call. `reduce_bars` is a stub that returns `f64::NAN`, and every IEEE-754
comparison against NaN is false — the engine's own comment says this is deliberate ("no trigger
fires regardless of direction or baseline type"). The proto discloses none of it; the comments read
as finished specifications. A client that configures a breakout alert gets a successful
`CreateAlert` and a permanently silent alert.

```
proto/poligun/ninniku/alert/alert.proto:149-151
  // Fires when the baseline price exceeds the highest high of the last
  // lookback_bars completed bars.
  message BreakoutAbove {

src/alert/alert_engine.rs:114-116
  // NaN is the safe sentinel: all IEEE 754 comparisons against NaN return false,
  // so no trigger fires regardless of direction or baseline type.
  f64::NAN
```

**Fix.** Disclose in the proto, or reject these variants at `CreateAlert` with a clear
`UNIMPLEMENTED` rather than accepting them into a dead state. Silently accepting is the worst of
the three options.

### F5 — `required_symbols` has no reader; nothing subscribes to market data (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:238`

The field's comment tells a client the engine subscribes on their behalf, and — critically — that
for a `NativeTrigger` this is "the only source of symbol information". Grepping all of `src/` for
`required_symbols` returns zero hits; the field is decoded and discarded. The only subscription
path in the service is the separate `Subscribe` RPC. A client that fills in `required_symbols` and
trusts the comment gets `latest_quote` → `Ok(None)` → an `ExecutionError` that is logged and
swallowed at `alert_bot.rs:82`, so the alert silently never fires.

```
proto/poligun/ninniku/alert/alert.proto:233-238
  // Symbols required across all triggers. The engine subscribes to market
  // data for these symbols once for the whole alert.
  // For BuiltInTrigger, this must include BuiltInTrigger.symbol.
  // For NativeTrigger, this is the only source of symbol information since
  // CEL expressions are opaque at parse time.
  repeated string required_symbols = 4;
```

**Fix.** Either have `CreateAlert` subscribe from this list, or change the comment to say the
client must call `Subscribe` separately. The current wording is the one that produces a dead alert.

### F6 — `NativeTrigger.initial_state` is never read; first evaluation always sees empty state (HIGH · mechanical · grounded)
`proto/poligun/ninniku/alert/alert.proto:53`

`AlertBot` initialises per-trigger state to `None` and the engine builds `context.state` solely from
that argument. `initial_state` appears once in `src/`, as a `None` constructor value in the
translator — a write, never a read. The telling detail: `TrailingAbove`/`TrailingBelow` need exactly
this seeding, and the translator solves it a completely different way, inlining the seed into the
generated CEL (`'hwm' in context.state ? context.state['hwm'] : {initial_wm}`). So the author needed
seed-state semantics, built a second mechanism for it, and left this field orphaned. A client
hand-writing the trailing-stop trigger this file uses as its worked example gets empty
`context.state` on the first tick.

```
proto/poligun/ninniku/alert/alert.proto:51-53
  // Seed state for the very first evaluation, accessible as context.state["key"].
  // On subsequent evaluations, TriggerResult.next_state takes precedence.
  optional google.protobuf.Struct initial_state = 4;

src/bot/alert_bot.rs:21
  trigger_states: Mutex::new(vec![None; trigger_count]),
```

**Fix.** Seed `trigger_states[i]` from `trigger.initial_state` at `AlertBot::new`. It's a one-line
change and it also lets the trailing-stop translator drop its bespoke seeding branch.

### F7 — `regular_hours` is undisclosed and unimplemented, while its two siblings are disclosed (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:193`

`MarketHoursFilter` explicitly labels `pre_market` and `post_market` "Not yet implemented" but
leaves `regular_hours` unmarked, and `EvalSchedule.market_hours_filter` documents meaningful absence
semantics ("If absent, the alert always evaluates"). Together those tell a reader that
`regular_hours` *is* honored. It isn't — a repo-wide grep for `market_hours`/`regular_hours` finds
matches only inside the proto itself, and `AlertBot` consults only `eval_schedule.interval`. A
client setting `regular_hours: true` on an equity alert gets it evaluated 24/7, firing on stale
overnight quotes and paging the user outside market hours.

```
proto/poligun/ninniku/alert/alert.proto:190-196
// Controls which market session windows are active for evaluation.
// pre_market and post_market are reserved for future implementation.
message MarketHoursFilter {
  bool regular_hours = 1;

  // Not yet implemented.
  bool pre_market  = 2;
```

**Fix.** Move the disclosure up to the message: nothing in `MarketHoursFilter` is implemented, so
say that once at the top rather than field-by-field. As written, the partial disclosure is what
does the damage.

### F10 — `percent_offset` doesn't say whether "5%" is `5` or `0.05`, and the repo uses both (HIGH · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:130`

`TrailingAbove`/`TrailingBelow` expose `Decimal percent_offset` with no unit stated anywhere; the
only nearby comment describes the `price_offset` case. The implementation treats it as a fraction
(`new_lwm * (decimal('1') + decimal('{}'))`). This repo's *other* percent field goes the other way:
`RenkoType.PricePercent` is consumed at `src/ta/renko.rs:148` as `1.0 + percent / 100.0`. So a
client — or a teammate — familiar with the sibling field sends `5` for 5%, gets a threshold at 600%
of the low water mark, and the alert never fires with no error at `CreateAlert`. Silent 100x errors
on money-adjacent fields are exactly what unit ambiguity buys.

```
proto/poligun/ninniku/alert/alert.proto:128-131
    oneof trailing_type {
      Decimal price_offset   = 1;
      Decimal percent_offset = 2;
    }

src/alert/mod.rs:89-90
  Some(AboveTrailingType::PercentOffset(d)) => (format!("new_lwm * (decimal('1') + decimal('{}'))", d.value), …)
```

**Fix.** Document the unit on both fields, and pick a convention across the repo rather than
per-message. If you keep fractions here while `PricePercent` uses percentages, name them differently
(`percent_offset` vs. `offset_fraction`) so the two can't be confused.

*Severity note: the reviewing agent proposed MEDIUM; the verifier raised it to HIGH after finding
the contradicting `renko.rs` convention in this same repo. I agree — this stopped being a
documentation gap once a second, opposite convention was found next door.*

### F9 — `time_unit` is a free-form string although `marketdata.TimeUnit` exists (MEDIUM · scoped · grounded)
`proto/poligun/ninniku/alert/alert.proto:94`

Three new fields (`Baseline.BarField.time_unit`, `BreakoutAbove.time_unit`,
`BreakoutBelow.time_unit`) model a bar interval as `string // e.g. "MINUTE"`, while this repo already
has `poligun.ninniku.marketdata.TimeUnit` and uses it as an enum on the public `GetBarsRequest` and
`GetRenkoChartsRequest`. Clients get no enumeration of legal values from the contract, and the
parser silently maps anything unrecognized to 60 seconds — so `"DAY"`, or a typo, yields a lookback
window quietly computed in minutes rather than an error.

```
proto/poligun/ninniku/alert/alert.proto:94
      string time_unit  = 2; // e.g. "MINUTE"

src/alert/mod.rs:207-211
  match time_unit.to_uppercase().as_str() { "MINUTE" => 60, "HOUR" => 3600, _ => 60, }
```

**Fix.** Reuse `marketdata.TimeUnit` — but note it currently only defines `TIME_UNIT_UNKNOWN` and
`TIME_UNIT_MINUTE`, so you'd extend it with `HOUR` (which the alert code already special-cases) and
whatever else you need. That's a shared-package change, not a local one, which is why this is SCOPED
rather than mechanical. Changing the field type after other teams build against it is wire-breaking,
so it's cheapest now.

---

## Design notes

*Opinions, not defects. These were demoted by verification — each is coherent but no verifier could
name a consumer who is actually harmed today.*

- **`AccountInfo` drops `pattern_day_trader` (7) and `daytrade_count` (21)** — the `reserved`
  markers are correct practice and are not the issue; the removal is. I searched all three clients
  in this tree (`src/`, the TypeScript frontend in `ninniku-fe/`, and the Python bindings under
  `analytics/`) and found no hand-written reader of either field, so nothing in this repo breaks.
  Two things still bother me: this has nothing to do with alerting, and it landed in commit
  `aad07b3` titled *"Bump dependnecies"* — a wire-breaking proto change inside a dependency-bump
  commit is precisely how breaking changes reach production unreviewed. **Open question:** were
  these removed because Alpaca stopped returning them, or because nothing here used them? If the
  latter, split it out of this branch. Either way, a deployed client still reading them now sees
  `false`/`0`, which is indistinguishable from "not PDT-flagged, zero day trades used" — the most
  dangerous possible default for a field that predicts order rejection.
- **`build.rs` drops serde derives for the whole `.poligun.ninniku.bot` package** — four deleted
  lines with package-wide reach. It's compulsory, not a style choice: `AlertBotParams` pulls
  `google.protobuf.Struct`/`Value` into the bot package and prost-types 0.14.4 has no `serde`
  feature at all, so the derive can no longer compile. `BotMetadata` persists to Redis as base64
  prost bytes, not JSON, and no in-repo consumer of those impls exists. The only cost is that the
  removal is invisible to anyone reading the proto diff, and `.poligun.ninniku.account` keeps its
  derive with no comment explaining the asymmetry. Worth one line in `build.rs` saying why.
- **The `Alert` message (`alert.proto:242`) is dead and its comment is wrong** — nothing in
  `proto/` or `src/` constructs or transmits it. Its comment says "Full alert record stored in
  AlertBotParams", but `AlertBotParams` holds an `AlertDefinition` (`bot.proto:45`) with the id
  living outside it in `BotMetadata.bot_id`. Delete it or wire it up; a stale comment on a dead
  message is the kind of thing a client author reads and plans around.
- **Read-back works, but only by convention.** I checked whether a client can read back what
  `CreateAlert` returns, since there's no `GetAlert` or `ListAlerts`. It can:
  `alert_id` *is* the `bot_id`, so `GetBotMetadata(alert_id)` returns the full `BotConfig` including
  `AlertBotParams.definition`, and `GetBotStatuses` enumerates ids for discovery. That works, but it
  is undocumented in the alert section of `ninniku.proto` and requires an N+1 to tell alerts from
  other bots. One sentence in the service comment — "read an alert back with GetBotMetadata; the
  alert_id is the bot_id" — would save every consuming team the same investigation I just did.

---

## Could not resolve

- **Whether any out-of-repo client reads `AccountInfo.pattern_day_trader` or `daytrade_count`.** I
  can see three clients in this tree and none use them, but I can't see other repositories or
  deployed binaries. What would settle it: a grep across whatever else consumes this service, or
  confirmation that `ninniku-fe` and `analytics/` are the only consumers.
