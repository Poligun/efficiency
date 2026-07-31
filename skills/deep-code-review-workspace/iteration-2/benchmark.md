# Benchmark — deep-code-review, iteration 2

| Eval | Config | Pass | Rate | Time (s) | Tokens | Tools |
|---|---|---|---|---|---|---|
| full-branch-review | with_skill | 18/18 | 100% | 2129 | 337,308 | 131 |
| full-branch-review | without_skill | 12/18 | 67% | 620 | 94,858 | 30 |
| narrowed-api-review | with_skill | 8/8 | 100% | 2509 | 259,009 | 82 |
| narrowed-api-review | without_skill | 6/8 | 75% | 441 | 64,857 | 19 |
| gating-dependency-bump | with_skill | 5/5 | 100% | 148 | 33,985 | 9 |
| gating-dependency-bump | without_skill | 3/5 | 60% | 731 | 47,353 | 33 |
| standalone-logic-hunt | with_skill | 10/11 | 91% | 1090 | 155,179 | 30 |
| standalone-logic-hunt | without_skill | 5/11 | 45% | 709 | 87,258 | 23 |

**with_skill** — 41/42 assertions (98%), 785,481 tokens, 98 min total

**without_skill** — 26/42 assertions (62%), 294,326 tokens, 42 min total

> with_skill runs in this iteration are clean re-runs against the decontaminated skill (f586e62 and later): the contamination checker (check_contamination.py) passed before any run was launched. An earlier set of iteration-2 with_skill runs for evals 2-4 turned out to predate the decontamination commit and is archived under with_skill-pre-decontamination/ (see PRE-DECONTAMINATION-NOTE.md); it is excluded from this benchmark. Baselines (without_skill) are the iteration-1 baseline runs carried over unchanged (byte-identical artifacts, verified) — they never load the skill, so decontamination does not affect them; the trade-off is that they were executed in a different session than the with_skill runs. Executors: claude-opus-5, dispatched sequentially from a Claude Fable 5 orchestrator session to keep timing measurements uncontended.

---

## Analyst pass

**The clean re-run reproduces the contaminated headline exactly: 41/42 (98%) vs 26/42 (62%).**
Iteration 1's fear — that eval-target contamination had inflated the with_skill numbers —
did not materialize in the totals. The per-eval profile shifted slightly (eval-1 improved
17/18 → 18/18; eval-4 slipped 11/11 → 10/11), but the aggregate is identical, and none of
the passes in this iteration can be attributed to leaked examples: the contamination checker
passed before any run launched, and graders verified finding evidence against the current
tree. Iteration 1's structural conclusions were therefore sound despite the tainted
instrument.

**Recall parity with the baseline still holds, and so does the fixture's discrimination
problem.** Both configurations again locate the injection, the lifecycle deadlock, the
missing dedup, the inverting fallbacks, and the unwired proto surface. The with_skill wins
remain concentrated in structure, precision, and disclosure — exactly iteration 1's
finding. The must-find assertions still cannot measure recall on this fixture; the
subtler second fixture (TODO P1 #5) is still the blocker for any recall claim.

**The one measured regression narrowed but did not close.** On the dependency-bump eval
the clean skill now catches the manifest/lockfile set mismatch and raises the hand-edited
lock suspicion — one of the three supply-chain facts iteration 1's baseline found and the
skill missed — while remaining cheaper than the baseline on both axes (34.0k vs 47.4k
tokens, 148s vs 731s) and now passing 5/5 vs 3/5. The reqwest TLS-backend default swap and
the MSRV jump remain unexamined: the `dependency` aspect (TODO P1 #4) is still needed for
those, since they require reading the bumped crate's release notes, which the early-stop
shape deliberately never does.

**One assertion failed, and it is cap-pressure shaped.** Eval-4's miss is a bundled
"five more declared surfaces have no consumer" roll-up table whose rows carry no execution
trace. Relatedly, eval-1's report self-declares "17 items against a soft cap of ~15" while
the mechanical counter sees 14 numbered findings — the S5 pass rests on the mechanical
definition. Both are the findings-cap ambiguity (TODO P1 #6) surfacing a third time:
what counts as "a finding" is undefined enough that runs bundle or split to fit, and the
cap still isn't enforced as a step.

**Environmental noise, disclosed.** Eval-1 lost 8 of 12 verifiers to upstream 529
Overloaded errors; eval-2 hit a ~40-minute harness tool outage that cut its verification
to 5 of 12 eligible findings and inflated its wall-clock. Both runs disclosed the
degradation in their Coverage sections and still passed every assertion — which says the
assertion set does not test verification *depth*, only its labelling and disclosure.
A future fixture should include at least one assertion only a verifier can settle.

**Cost.** 785k tokens / 98 min with_skill vs 294k / 42 min baseline (~2.7× / ~2.3×;
the token figure includes 529-retry overhead in eval-1 and redone work in eval-2, so the
clean-conditions ratio is somewhat lower — iteration 1 measured 2.1× under no outages).
The cost conclusion is unchanged: the skill buys trustworthy structure, not recall, and
the P2 cost items (conventions.md reuse, A1/A2 merge decision) are where that ratio
comes down.
