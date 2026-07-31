# Benchmark — deep-code-review, iteration 1

| Eval | Config | Pass | Rate | Time (s) | Tokens | Tools |
|---|---|---|---|---|---|---|
| full-branch-review | with_skill | 17/18 | 94% | 2258 | 207,324 | 53 |
| full-branch-review | without_skill | 12/18 | 67% | 620 | 94,858 | 30 |
| narrowed-api-review | with_skill | 8/8 | 100% | 2173 | 127,818 | 39 |
| narrowed-api-review | without_skill | 6/8 | 75% | 441 | 64,857 | 19 |
| gating-dependency-bump | with_skill | 5/5 | 100% | 123 | 29,833 | 8 |
| gating-dependency-bump | without_skill | 3/5 | 60% | 731 | 47,353 | 33 |
| standalone-logic-hunt | with_skill | 11/11 | 100% | 1526 | 247,861 | 53 |
| standalone-logic-hunt | without_skill | 5/11 | 45% | 709 | 87,258 | 23 |

**with_skill** — 41/42 assertions (98%), 612,836 tokens, 101 min total

**without_skill** — 26/42 assertions (62%), 294,326 tokens, 42 min total

> with_skill runs used a version of the skill that contained examples drawn from this eval target. Findings matching those examples are not independent evidence. Contamination was removed after the run; iteration 2 re-measures.

---

## Analyst pass

**42 paired assertions: 15 discriminate, 26 don't, 1 fails on both, 0 favour the baseline.**

### Where the skill actually wins

All 15 discriminating assertions are about **structure, precision, and disclosure** — none
are about finding more bugs:

- severity + fix-clarity labels, quoted evidence, severity ordering (4)
- a Coverage statement saying what ran and what didn't (3)
- execution traces on every finding (1)
- not falling for the "missing tests" trap; not inventing findings about untouched code (2)
- correctly declaring a branch un-reviewable instead of manufacturing findings (1)
- angle disclosure, an intent-questions section, proposed-not-written memory, and no
  finding resting on inferred intent (4)

### Where it doesn't

**26 of 42 assertions are non-discriminating, and they are mostly the must-find ones.**
Both configurations locate the injection, the lifecycle gap, the missing dedup, the silent
fallbacks, and the unwired proto surface. On this branch, a capable agent with no skill at
all finds the bugs.

That is the honest headline: **recall is not where this skill earns its cost.** It earns it
by making the output trustworthy — labelled, anchored, ranked, and explicit about its own
gaps — and by not filing findings a careful reviewer wouldn't. Whether that is worth ~2×
tokens and ~3× wall-clock is a judgment call, and it depends on whether the reader is
acting on the report or just skimming it.

Two consequences for iteration 2:

1. **The must-find assertions have little discriminating power on this fixture.** Keep them
   as a regression guard, but a second fixture with subtler bugs is needed to measure recall
   at all.
2. **The `≤15 findings` cap failed in both configurations** (with_skill 17, baseline 27).
   The instruction isn't landing. Either enforce it as a hard truncation step or drop it and
   measure something else — an instruction that is stated and then ignored teaches the model
   that the other caps are soft too.

### Cost

| | assertions | tokens | wall-clock |
|---|---|---|---|
| with_skill | 41/42 (98%) | 612,836 | 101 min |
| without_skill | 26/42 (62%) | 294,326 | 42 min |

The gating eval is the one case where the skill is cheaper on both axes (29.8k/2min vs
47.4k/12min) — but see `meta/IMPROVEMENTS.md`, it bought that by skipping real
supply-chain risk the baseline found.
