# Ground truth — billing-service `feat/refunds-and-credits`

Second eval fixture, built 2026-07-30. Python + OpenAPI, deliberately **not** Rust — the
skills claim to be language-agnostic and iteration 1 never tested that.

Fixture: `deep-code-review-workspace/fixtures/billing-service`
Base `main` → `feat/refunds-and-credits`. 5 files, +187 lines.
`scope_detect.py`: `shape: standard`, all four aspects active (`code_api` and `logic`
strong), 187 code lines across 5 code files.

## Why this fixture exists

On the ninniku fixture, 26 of 42 assertions were non-discriminating — a capable agent with
no skill finds those bugs. The bugs here are **planted to require tracing rather than
pattern-matching**: each one looks correct in isolation, and several are contradicted only
by a sibling function or a docstring elsewhere in the same file.

Every bug below was verified by running the code, not by reading it.

---

## Must find

| # | Finding | Anchor | Angle | How it was verified |
|---|---|---|---|---|
| B1 | **Double-counted billing boundary.** `usage_for_invoice` uses `occurred_at >= $2 AND occurred_at <= $3` — inclusive at both ends — while the sibling `usage_between` in the same file documents and uses the half-open `< $3`. A usage record landing exactly on a period boundary is billed in two consecutive invoices. | `src/billing/invoices.py` (`usage_for_invoice`) | A3 boundary | read; contradicted by the sibling 20 lines above |
| B2 | **Idempotency key is not idempotent.** `idempotency_key` mixes `datetime.utcnow()` into the hash material, so every redelivery of the same event produces a different key and the duplicate check never fires. The docstring claims the opposite: *"Stable key so a redelivered webhook is not processed twice."* | `src/billing/webhooks.py` (`idempotency_key`) | A2 repeat-fire | read; docstring contradicts behavior |
| B3 | **Batch loop reports only the last item.** `refund_batch` **reassigns** `result` on each iteration instead of accumulating, so a batch where the first N fail and the last succeeds returns `processed: 1, failed: 0`. | `src/billing/refunds.py` (`refund_batch`) | A5 partial failure | **ran it**: 3 requests, first 2 fail → returned `{'processed': 1, 'failed': 0}` |
| B4 | **Currency fallback silently changes the amount.** `to_usd_cents_or_par` catches bare `Exception` and returns the raw amount when no rate exists, so ¥10,000 (~$67) is credited as $100.00. It also swallows every unrelated error on that path. | `src/billing/refunds.py` (`to_usd_cents_or_par`) | A4 fallback | **ran it**: `to_usd_cents_or_par(10000, "JPY")` → `10000` |
| B5 | **Refund matched by amount, not identity.** `find_charge_for_refund` selects on `amount_cents` with `ORDER BY captured_at DESC LIMIT 1`. An account with two identical charges gets the most recent one refunded regardless of which the request meant. | `src/billing/refunds.py` (`find_charge_for_refund`) | A9 identity | read; the SQL is the evidence |
| B6 | **`dry_run` is declared and ignored.** The OpenAPI spec documents it as *"Validate and report the outcome without persisting anything"*; `adjust_credits` accepts the parameter and never reads it, so a dry run mutates the balance. | `api/openapi.yaml` + `src/billing/handlers.py` | A6 declared surface | `grep dry_run` — bound but never referenced |
| B7 | **Errors returned as HTTP 200.** `/v1/credits/adjust` documents `"200: Adjustment result. Check `error` to detect failure."` and the handler returns `{"error": ...}` on failure. Clients that check status codes treat every failure as success. | `api/openapi.yaml`, `src/billing/handlers.py` (`adjust_credits`) | API design (honesty) | read |
| B8 | **Bare exceptions across a module boundary.** `refunds.py` raises `ValueError` where README and 6 sibling classes across 4 modules establish `BillingError` subclasses. This is the one convention finding, and the ledger should rate it `established`. | `src/billing/refunds.py` (`find_charge_for_refund`) | convention | counted: 6 subclasses, 0 counterexamples |

**Secondary (credit if found, not required):** `adjust_credits` overloads grant and deduct
on the sign of `delta_cents` (decoupling); `refund_one` credits the balance *before*
marking the charge refunded with no transaction, so a crash between them double-credits on
retry (A5); `handlers.adjust_credits` catches bare `Exception` and stringifies it.

---

## Must NOT find

Each is a plausible finding the repo itself contradicts.

| Trap | Why it's wrong |
|---|---|
| **"`settlement_delay_days` is unimplemented"** | The spec says so *in the spec*: `"Not yet implemented; accepted and ignored."` That's disclosure, which the false-positives list explicitly protects. Contrast with B6, where the promise is in the spec and only the code reveals it's a lie — the asymmetry is the point of the pair. |
| **"`ADJUSTMENT_SOFT_LIMIT = 0.25` uses float for money"** | It's a *ratio*, not an amount. README says money is `Decimal` in minor units, and every actual amount in the diff obeys that. |
| **"No tests"** | The repo has zero test files on either branch. No convention exists to violate — ledger verdict `absent`. |
| **"SQL should be extracted to a query layer"** | README states the convention explicitly: *"Repository modules expose `pub`-style functions and keep SQL in the same module."* The new code follows it. |
| **"`datetime.utcnow()` is deprecated"** | A linter's job. Also note it appears in B2 for a completely different reason — the finding there is the *non-determinism*, not the deprecation. A report that flags the deprecation and misses the idempotency bug has failed B2. |

---

## What this fixture measures that ninniku doesn't

- **Language-agnosticism.** Python + OpenAPI rather than Rust + protobuf.
- **Recall on non-obvious bugs.** B1, B2, B3, and B5 all read as correct code; each needs a
  trace or a comparison against a sibling to see. If both configurations still find
  everything here, the skill's value really is confined to structure and the recall
  question is settled.
- **The disclosure asymmetry** (B6 vs `settlement_delay_days`) as a paired discriminator in
  one diff — a reviewer that treats them the same is wrong either way.
- **A clean convention signal** — 6 supporting occurrences, 0 counterexamples, plus a
  written README rule. Unlike ninniku, the establishment test should fire cleanly here, so
  a *missed* B8 is a real failure rather than a defensible `mixed` call.
