# business-logic-review — improvement checklist

The memory protocol is the risky part of this skill and the part most worth iterating on.
The angles are comparatively safe: if one has low yield, cut it.

## Angles

- [ ] **Measure per-angle yield.** Track which angle produced each finding through to the
      report, across several branches. A10 (concurrency) is already suspected of being the
      lowest-yield and highest-false-positive angle — it's gated for that reason, but the
      suspicion is untested.
- [ ] **A "removed behavior" angle.** For every deleted line, name the invariant it
      enforced and find where the new code re-establishes it. Currently only an edge-case
      note for pure refactors. It's the highest-value angle for refactor branches and it
      has no owner.
- [ ] **Angle-specific false positives** are listed per angle but haven't been validated.
      Some are probably missing; the way to find out is to look at what verifiers refute.
- [ ] Consider a **retry/at-least-once semantics** angle distinct from A2. Idempotency and
      retry-safety overlap but aren't the same question, and distributed systems fail at
      the seam.

## Memory protocol

- [ ] **Measure the spurious-BROKEN rate.** The anchor-quote mechanism is expected to
      produce ~10-20% false BROKEN after a refactor. If it's much higher, the "quote
      something durable" instruction isn't landing and needs to be more prescriptive.
- [ ] **Semantic inversion is undetectable** — `>=` becoming `>` on a line whose quoted
      token didn't change. Documented as a known limit. A fix might anchor to a normalized
      form of the expression rather than raw text.
- [ ] **Absence claims are the weakest entries.** A negative grep can miss a synonym. The
      current mitigation (widen by one synonym, cap severity at MEDIUM) is a guess; worth
      checking whether it's enough.
- [ ] **The open-question loop is unproven.** The whole knowledge-acquisition story depends
      on humans actually answering the questions. If they don't, the questions file grows
      and nothing gets promoted to confirmed intent. Watch for this — and if it happens,
      the fix is probably fewer, better questions rather than more.
- [ ] **No conflict resolution between two knowledge bases** when both repo and personal
      trees exist. Currently "read both, repo first" — undefined what happens when they
      contradict.
- [ ] **`re_raised` counting requires matching a new finding to an old refutation**, which
      is fuzzy. Needs a real matching rule, or the counter never increments and the
      "propose an inline comment at 3" hygiene signal never fires.

## Output and integration

- [ ] **The behavior model (Step 3) isn't in the output.** It's the reviewer's scaffolding,
      but a human might want to see it — it's often the clearest summary of what the
      feature does that anyone has written. Cheap to include, and worth testing whether
      readers value it.
- [ ] **`intent_dependency: unresolved` grouping** is specified for the orchestrator but
      untested. The idea — group shaky findings into one question rather than shipping
      several — is good and unproven.
- [ ] Test **standalone mode** properly. Everything so far is designed around subagent
      dispatch; the human-facing path has had less thought.

## Open questions

- Is the 400-line threshold for "checklist inline vs one subagent per angle" right? Picked
  by judgment. The tradeoff is real (one reviewer holding the whole model beats ten holding
  fragments) but the crossover point is a guess.
- Should the skill ever write memory in subagent mode if the orchestrator explicitly
  delegates approval? Currently a hard no, which is safe but might be over-strict.
- The severity cap for doc-provenance findings (MEDIUM) may be too aggressive. A contract
  that promises something the code doesn't do can be genuinely severe.
