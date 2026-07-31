# The angles

Load the sections whose gate fired. Each angle is a named lens with a hunting procedure,
grep seeds, an evidence bar, and the false positives it specifically tends to produce.

Named angles beat one long checklist for a reason worth knowing: a checklist gets skimmed
and produces a uniform shallow pass, while a named lens with its own procedure produces a
deep pass on one dimension. Run several and you get coverage; run a checklist and you get
the appearance of coverage.

**Contents:** [A1 Lifecycle](#a1--lifecycle-auditor) · [A2 Repeat-Fire](#a2--repeat-fire--idempotency)
· [A3 Boundary & Window](#a3--boundary--window-analyst) · [A4 Fallback & Sentinel](#a4--fallback--sentinel-auditor)
· [A5 Partial Failure](#a5--partial-failure-tracer) · [A6 Declared Surface](#a6--declared-surface-auditor)
· [A7 Taint](#a7--taint-tracer-conditional) · [A8 Numeric Domain](#a8--numeric-domain-auditor-conditional)
· [A9 Identity](#a9--identity--correlation-auditor-conditional) · [A10 Concurrency](#a10--concurrency--reentrancy-auditor-conditional)

---

## A1 — Lifecycle Auditor

**Question.** For every entity with a lifecycle, which transitions can nobody perform,
which states have no exit, and what gets created but never released?

**Procedure.** Build an explicit matrix. States down one axis, operations across the
other. For each cell ask: what code performs this, and what state does it require?

Then look for three shapes:

- **The unreachable transition.** An operation requires state S, and no code path ever
  puts an entity into S. Or the reverse: an operation refuses state S, every entity is in
  S, and nothing moves them out first. Follow the *actual* call sequence — a create that
  always starts something, followed by a delete that refuses started things, is a
  guaranteed failure that looks fine in each function separately.
- **The terminal state.** An entity can enter a state it can't leave, and nothing cleans it
  up.
- **The orphan.** Something registered, spawned, allocated, or subscribed on one path,
  with no corresponding removal on every exit path — including the error paths.

**Seeds.** `create|new|start|spawn|register|open|acquire|subscribe` paired with
`delete|stop|close|release|unregister|cancel|drop`. Grep for status or state enums and
find every write.

**Evidence bar.** Name the exact call sequence that produces the stuck state, with each
step's `file:line`.

**Its false positives.** Transitions unreachable only through code the branch didn't touch.
Cleanup handled by a framework, a destructor, or a scope guard you didn't look for.

---

## A2 — Repeat-Fire & Idempotency

**Question.** What happens when this runs again and nothing has changed?

**Procedure.** List every externally visible effect — notify, send, charge, order, write,
publish, retry. For each, find what makes it happen at most once when it should happen at
most once. That's an edge transition (fired now, wasn't before), a cooldown timestamp, a
dedup key, or a persisted "already did this" marker.

Then ask three follow-ups the first pass usually misses: does it survive a restart? does it
survive a retry after a partial failure? does it survive the same event arriving twice?

**Seeds.** `cooldown|debounce|throttle|dedup|idempot|already|last_fired|last_sent|seen|
processed`. A **negative** result here — no matches — is itself the finding, and it's one of
the most valuable results in this whole document.

**Evidence bar.** Trace it concretely: this condition holds, the loop runs every N, so the
user gets M messages an hour. The number is what makes it land.

**Its false positives.** Effects that are genuinely level-triggered by design (a gauge, a
heartbeat, a reconciliation loop). Dedup implemented downstream at the sink — check before
claiming it's absent.

---

## A3 — Boundary & Window Analyst

**Question.** For every range, window, or interval: who advances the low end, is it
inclusive at both ends, how many clocks are involved, and what do the first and last
iterations look like?

**Procedure.** Find every window. For each, answer in writing:

1. Where does `a` come from, and where does it get advanced? Is it advanced even when the
   work failed — which would silently skip that window forever?
2. Where does `b` come from? Is it sampled once per batch or once per item? Different
   samples inside one logical operation leave uncovered gaps between them.
3. Inclusive or exclusive at each end? A window that's inclusive at both ends
   double-counts the boundary; the standard is half-open for a reason.
4. What is the **first** window, before there's any history? A default that makes `a == b`
   produces a zero-width window that matches nothing, forever, silently.
5. How many clocks? Client vs server vs database time, or two calls to `now()` inside one
   operation, both introduce skew.

**Seeds.** `now()|Utc::now|time.Now|Date.now|currentTimeMillis`, `last_|since|from_|until|
_at`, `>=|<=` in range comparisons, timezone and DST conversions.

**Evidence bar.** Name the specific interval of time or range of values that falls in the
gap, or the specific boundary element counted twice or zero times.

**Its false positives.** Off-by-one claims on windows where the boundary element is
genuinely idempotent. Clock-skew claims where a single clock is used throughout.

---

## A4 — Fallback & Sentinel Auditor

**Question.** For every default-on-failure, does the default flip the decision it feeds?

This is usually the highest-yield angle, because the code *looks* defensive. Substituting
zero for a failed parse reads as careful error handling right up until you notice it makes
`price >= threshold` compare against zero — which is always true.

**Procedure.** Find every place a failure produces a value instead of an error:
`unwrap_or`, `??`, `||`, `.getOrElse`, `catch { return default }`, `NaN`, `-1`, `0`,
empty string, empty collection, `null` coalescing.

For each, do two things:

1. **Trace the value forward** into the comparison, branch, or arithmetic it reaches.
   Ask what that operation does with the sentinel. Pay attention to sentinels with
   surprising semantics — `NaN` compares false against everything including itself, and
   many `max`/`min` implementations silently return the *other* operand when given one, so
   a running maximum seeded with `NaN` freezes instead of erroring.
2. **Ask who finds out.** A fallback that logs a warning nobody reads and returns a wrong
   answer is worse than a crash, because the wrong answer propagates.

Also check the *inverse* pair: one fallback that makes a condition always true and another
that makes it always false are both present in the same file more often than you'd think.

**Seeds.** `unwrap_or|unwrap_or_else|unwrap_or_default|\?\?|\|\||getOrElse|orElse|
except:|rescue|catch|NaN|f64::NAN|-1|None =>`.

**Evidence bar.** Name the input that triggers the fallback and the decision it inverts.

**Its false positives.** Fallbacks feeding a value that's genuinely optional downstream.
Defaults in configuration loading, where a documented default is the point.

---

## A5 — Partial-Failure Tracer

**Question.** When something fails mid-way, what work is abandoned, what state is left
half-updated, and can anyone who could act actually see it?

**Procedure.** For every loop or batch over independent items, find the error handling.
Does one item's failure abort the rest? That's correct for a transaction and wrong for
independent work — decide which this is from the behavior model, and note that "any of
these can fire" semantics in a contract implies independence.

For every multi-step mutation, ask what's already been committed when step 3 fails, and
whether anything rolls it back. Persisting a record and then failing to start the thing it
describes leaves an orphan the caller never learns about.

Then trace failure visibility: does it reach a human, a metric, or a status field — or
only a log line?

**Seeds.** `for .* { .*\?` (error propagation inside a loop), `try|catch|except|recover`,
`continue` vs `break` vs `return` in error branches, transaction and rollback boundaries.

**Evidence bar.** Name the failing step, the specific work skipped as a result, and the
state left behind.

**Its false positives.** Abort-on-first-error where the items genuinely are a transaction.
Retry logic elsewhere that you didn't look for.

---

## A6 — Declared-Surface Auditor

**Question.** Does every declared field, flag, and documented behavior have a real
consumer?

Nearly a grep, and it reliably finds real problems — declared-but-unwired surface is one of
the most common defects in feature branches, because the contract gets written first and
the last few fields never get connected.

**Procedure.** List every field, option, config key, and documented behavior the change
declares. Grep each name across the implementation. Sort the results:

- **No reader at all** → dead weight, or a lie to the caller who sets it and expects an
  effect. Which one depends on whether the contract documents an effect.
- **Written but never read** → same thing, one step later.
- **Documentation contradicts implementation** → report both anchors. This is high-value
  and easy to confirm: the doc comment says an operation is unconditional, the code rejects
  half its inputs.

**Seeds.** For each declared name, `rg -w '<name>'` and check whether the only hits are the
declaration itself and generated code.

**Evidence bar.** The declaration's `file:line`, the grep you ran, and what it found.

**Its false positives.** Fields the contract *itself* marks as not yet implemented — that's
disclosure, not a defect. Fields consumed by generated code or reflection. Fields read in
another repo you can't see, which you should say rather than assume either way.

---

## A7 — Taint Tracer *(conditional)*

**Gate.** The diff builds a string that something later interprets: SQL, shell, a path, a
template, an expression language, a regex, a query DSL.

**Question.** Can caller-controlled input change the *structure* of what gets interpreted,
rather than just the values in it?

**Procedure.** Find every place external input is concatenated or interpolated into a
string that is later parsed, compiled, or executed. Walk backward from each interpolation
to where the value entered the system, and look for validation on that path — character
class, length, parse-into-a-typed-value, allowlist. Absence of validation is the finding;
the escape sequence that exploits it is the trace.

Check the whole family. If one builder interpolates unvalidated input, its siblings almost
certainly do too — report the pattern with a representative anchor rather than fifteen
near-identical findings.

**Seeds.** `format!|f"|sprintf|+ str|.join(|`${`|% s` near `execute|query|compile|eval|
parse|Command::new|system|exec`.

**Evidence bar.** The exact input that breaks out, and what it changes the interpreted
structure into.

**Its false positives.** Input that's already been parsed into a typed value upstream.
Parameterized queries where the interpolation is only in a non-data position you verified.

---

## A8 — Numeric Domain Auditor *(conditional)*

**Gate.** Arithmetic on externally-supplied numbers, unit conversion, or money.

**Question.** What are the actual domains of these values, and what happens at the edges?

**Procedure.** For each arithmetic expression on external input: can it overflow, wrap, or
panic? Are negative values possible and what do they mean? Is there a division that can be
by zero?

For unit conversion, check the fallthrough case specifically — a `match` on a unit string
with a default arm silently produces a wrong-by-a-large-factor result for any unit the
author didn't list, and "silently wrong by 1440×" is much worse than an error.

For money, any conversion to a binary float is a precision finding, and it's a stronger one
when the codebase has a decimal type it's converting *away from*.

**Seeds.** `* |+ |<< ` on values from a request; `as i32|as u32|int(|parseInt`;
`match .*unit|_ =>|default:`; `f64|float|double` near `price|amount|total|balance`.

**Evidence bar.** The input value and the resulting wrong number.

**Its false positives.** Overflow on values bounded by validation you didn't read.
Float usage where the codebase has no decimal type and precision genuinely doesn't matter.

---

## A9 — Identity & Correlation Auditor *(conditional)*

**Gate.** Things matched by index, position, or order rather than a stable identifier.

**Question.** What happens when the collection is reordered, shortened, or an element is
replaced?

**Procedure.** Find every parallel array, positional state vector, or index-keyed map.
Ask: can the thing being indexed *change* while the index-keyed data persists? Can a
configuration update replace the list while the state survives?

Look specifically for containers that only ever grow. Code that extends a state vector to
match a new length, but never shrinks or clears it, silently rebinds one element's history
to a different element after a removal.

**Seeds.** `\[i\]|\.get(i)|enumerate()|zip(`, `while .*len() < |resize|extend`, state
stored as `Vec<Option<` or an array parallel to a config list.

**Evidence bar.** The specific reordering or removal, and which element ends up with which
element's data.

**Its false positives.** Positional matching where the collection is provably immutable
after construction — but check that claim, because "immutable today because the update path
is unimplemented" is a latent finding worth recording at lower severity.

---

## A10 — Concurrency & Reentrancy Auditor *(conditional)*

**Gate.** Locks, channels, task spawning, cancellation, or shared mutable state.

**Question.** What breaks when two of these run at once, when one is cancelled mid-way, or
when a channel falls behind?

**Procedure.** For each lock, note what's held across what. A lock held across a blocking
or awaiting call is a stall waiting to happen. For each shared value read then written in
separate critical sections, ask what happens if something else writes in between.

For channels, check the behavior when the buffer overflows or the receiver lags — some
receive patterns treat a lag error as terminal, which silently stops delivery to that
consumer forever. For spawned work, check cancellation: what's left half-done?

**Seeds.** `lock()|Mutex|RwLock|synchronized`, `spawn|go |Task::|async`,
`select!|recv()|Lagged|Closed`, `block_on|block_in_place` inside sync callbacks.

**Evidence bar.** Name the two concurrent paths and the interleaving that breaks.

**Its false positives.** "Race condition" with no second holder identified — this angle
produces more speculative findings than any other, so hold it to a higher bar. If you can't
name the other task, don't report it.
