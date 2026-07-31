# Severity, fix clarity, and ordering

Load this when ranking findings (Step 7) or when writing an agent's output contract
(Step 4).

## The finding schema

```yaml
id: F3
aspect: wire_api | code_api | logic | convention
severity: CRITICAL | HIGH | MEDIUM | LOW     # impact; assigned by the orchestrator
fix_clarity: MECHANICAL | SCOPED | NEEDS-DECISION
title: "…"                                    # ≤70 chars, the claim alone, no rationale
anchor: "<path>:<line>"                       # exactly one, and it must exist
committed: true | false                       # routes inline comment vs summary body
description: "…"                              # 2-4 sentences ending in the consequence
evidence: ["file:line + quoted code", …]      # quoted from the CURRENT working tree
verdict: CONFIRMED | PLAUSIBLE | GROUNDED | TASTE
corroborated_by: [A1, A3]                     # omit when single-source
open_question: "…"                            # required iff fix_clarity is NEEDS-DECISION
```

## Severity is impact, not confidence

How sure you are is already carried by `verdict`. Mixing the two produces reports where
everything obvious is CRITICAL and everything subtle is LOW, which is backwards.

**CRITICAL** — ships wrong behavior to a user, or breaks an existing client. Data loss,
silent wrong answers, an operation that can't succeed, a deployed contract that stops
working.

**HIGH** — a real defect with bounded blast radius, **or an API shape that will require a
breaking change to fix later**. Fix before merge.

That second clause carries weight. Without it, design findings are structurally capped at
MEDIUM — nothing is *broken* today — and the API aspect quietly becomes decorative. "This
works now and will cost a migration in six months" is a legitimate HIGH, and saying so
before merge is the entire point of reviewing a design while it's still cheap to change.

**MEDIUM** — real, but on a secondary path, or the cost is developer time rather than user
harm. Also the ceiling for `PLAUSIBLE` findings and for anything resting on documented
intent rather than confirmed intent.

**LOW** — hygiene. A local inconsistency, a cosmetic contract wart, a stray debug line.
Worth saying once, not worth arguing about.

**NOTE** — not a severity. The bucket for `TASTE` verdicts and `mixed` ledger rows.
Rendered unranked at the bottom under "Design notes", explicitly labelled as opinion.

## Fix clarity is an independent axis

The reader's question isn't only "how bad is this" but "can I deal with it now, or does
this need a conversation".

**MECHANICAL** — a determinate edit; anyone applies it without deciding anything.
*"Remove the leftover debug log — it fires on every iteration, not just the failing one."*

**SCOPED** — the required change is clear, more than one reasonable implementation exists,
the author picks. *"Cached state has to be invalidated when its key set changes — key it
by identity, or clear it on update."*

**NEEDS-DECISION** — needs a human product or architecture call the reviewer can't make.
Carries a mandatory `open_question`. *"Is this a first-class resource with its own store,
or permanently a field on its parent? That answer determines whether the ids can differ,
whether a list operation exists, and what delete is allowed to touch."*

A finding that rests on **inferred** intent — the reviewer's guess about what the code was
supposed to do, with nothing to source it to — is not a finding at all. It's an
open question with `fix_clarity: NEEDS-DECISION`. State the assumption and ask.

## Ordering

1. Severity, descending.
2. Within a band, fix clarity **ascending** — MECHANICAL first.
3. **One override:** any CRITICAL or HIGH with NEEDS-DECISION is pinned above everything
   else, in its own "Needs a decision before merge" section.

Rule 2 is about momentum. A reader who gets three fixes they can apply immediately arrives
at the hard one already engaged; a reader who opens with a question requiring a meeting
tends to close the tab. Rule 3 exists because those are the only findings with human
latency in them — if a decision has to be made, it should start being made on the first
screen rather than after the quick wins.

Rendered heading:

```
### F3 — Alert state survives a trigger-list change (HIGH · scoped · confirmed)
```

## Caps and honesty

Cap the report at roughly 15 findings. Beyond that, readers stop distinguishing between
them and the review functions as noise regardless of how correct it is.

When you cut, correctness outranks design and hygiene. But say what you cut, in the
Coverage line — a truncation the reader doesn't know about is worse than the truncation
itself, because it reads as "we checked everything and found this much."

The same applies to verification. Anything not verified is stamped `unverified`. Never let
the report imply a check that didn't run.
