# Decision log

Why the skill is shaped the way it is. The **rejections** are the valuable half — they're
what a future iteration would otherwise rediscover the hard way.

## Accepted

**Deterministic scope detection in a script, not model judgment.**
The report claims "aspect X did not run"; that claim has to be reproducible or the whole
gating story is untrustworthy the first time someone re-runs and gets a different answer.
It's also cheaper, and it keeps the orchestrator from reading the full diff and forming
opinions *before* it has to arbitrate between agents that did.

**Range is `git diff <merge-base>` with no second ref.**
Compares merge-base to the working tree, so committed and uncommitted changes are in one
range. Reviews usually run before the commit, and a stray debug line is worth catching then.
Cost: uncommitted findings can't become inline PR comments, so the report partitions them.

**Base resolution prefers trunk refs over `@{upstream}`.**
Found during unit testing: on a pushed feature branch, `@{upstream}` resolves to the
branch's own remote ref and the diff collapses to whatever is uncommitted. Trunk refs come
first, and any candidate that's an ancestor-equal of HEAD is skipped.

**The establishment test (≥3 support, ≤1 counterexample).**
Convention review has to work in a repo with no CLAUDE.md, and the obvious-looking
convention is often contradicted by the codebase itself. Counting is what separates a
convention from a coincidence. A `mixed` verdict means *both sides lose* — it becomes a
note about repo inconsistency rather than a finding against the author.

**Convention inference stays in the orchestrator; only checking is delegated to a cheap model.**
Small models check explicit rules well and infer them badly. Splitting the task along that
seam is what makes the cheap tier viable at all. This is the concrete answer to "which work
goes to cheap models."

**Two verdict vocabularies, split by claim type.**
`CONFIRMED/PLAUSIBLE/REFUTED` for logic (uncertainty → dropped), `GROUNDED/TASTE/REFUTED`
for design (uncertainty → demoted, kept). See the rejection of confidence scoring below.

**Severity and fix-clarity as independent axes, with MECHANICAL sorted first within a band.**
The reader's question isn't only "how bad" but "can I deal with this now." Cheap fixes
first builds momentum before the one that needs a meeting. The one override — CRITICAL/HIGH
+ NEEDS-DECISION pinned to the top — exists because those are the only findings with human
latency in them.

**Memory stores pointers and questions, never evidence.**
The constraint that makes every other memory rule safe. A finding's evidence is always code
quoted from the current tree this session, so a stale entry can at worst waste a lookup —
it cannot produce a wrong finding.

**One round 2, ≤2 agents, narrow questions, no round 3.**
Round-2 output goes through verification but not back through arbitration, so it can't
create a conflict that would justify another round. Unresolved items get disclosed in a
"Could not resolve" section — disclosure closes the loop where another round wouldn't.

**One shared knowledge base across all three skills.**
Splitting review memory from indexed knowledge would mean two indexes, two routing
conventions, and a migration the first time they cross-reference.

## Rejected

**Numeric confidence scoring with a threshold filter** (the pattern the `code-review`
plugin uses: score 0-100, drop below 80).
Right for "is this bug real," which is binary and checkable. Wrong for design opinions — ask
a model to score "this API shape will need a breaking change to fix later" and it lands at
40-70, because a taste judgment can't be "absolutely certain." The filter would silently
delete the entire API aspect, and silently is the problem: the review would look like it
ran and found nothing.

**Time-based memory expiry / decay.**
Age doesn't correlate with truth. A two-year-old invariant in untouched code is fine; a
two-week-old one in a hot file may already be dead. Worse, expiry deletes the expensive
human-confirmed entries — exactly the ones that can't be cheaply rebuilt. Replaced with
change-triggered revalidation: decay by `git log` against the anchor, not by clock.

**Deleting refuted findings, or suppressing their whole class.**
Deleting means re-litigating every review. Class-wide suppression hides genuinely new
instances. Resolved by recording the *reason as a re-checkable predicate* with a
`guard_anchor` — the refutation voids automatically when its guard disappears, and default
scope is this-site-only.

**A blanket "resource lifecycle" angle**, separate from A1.
Zero unique hits against the eval target; everything it would catch is already a
state × operation matrix hit. Two angles fighting over the same evidence produces
duplicates the orchestrator has to dedup.

**A test-coverage angle.**
Produces advice, not defects. "Add tests" is a project decision, and in a repo with two
test modules total it's not even a convention violation.

**A ninniku worked-example reference file.**
Would overfit the skill to its own eval target. The angles and rubric have to generalize;
baking one branch's specifics into a reference file is how a skill starts scoring well on
its benchmark and badly everywhere else.

> **And then iteration 1 did it anyway, inline.** The dedicated file was rejected, but
> examples drawn straight from the eval target were written into `SKILL.md`, the severity
> rubric, the memory protocol, and the output contract — including one keyed to a change
> that existed only in the uncommitted working tree, and a *fabricated* `user-quote` in the
> memory template. An eval agent caught it and correctly discounted its own findings.
>
> The lesson generalizes past this skill: **rejecting a bad artifact doesn't prevent the
> behavior that artifact represented.** Examples get written while the author's head is
> full of the case they just debugged, and that case is usually the eval target. All
> examples are now synthetic, and each carries an explicit "write your own from the code in
> front of you" instruction. Iteration 2 should audit for this before running evals, not
> after — `grep` the skill tree for identifiers from the eval repo.

**Letting subagents write memory directly.**
A subagent can't obtain user approval, and several siblings writing the same file is a
merge conflict by construction. They return proposals; the orchestrator batches and asks
once, before dispatch.

**Treating an empty result as failure.**
Only an aspect at `strength: strong` returning zero findings warrants a second look. A
reviewer that treats silence as failure manufactures findings to fill it — which is worse
than missing one.

## Open

- Whether `code_api` and `wire_api` should stay separate agents. They corroborate each
  other often, which is useful, but it's also two Opus calls where one might do.
- Whether the ≤12 verifier cap binds in practice on larger diffs, and whether severity
  order is the right thing to cut on.
- Whether `focused` shape should skip business logic too. Currently it doesn't — keeping
  logic out of the orchestrator's context was an explicit requirement — but on a 50-line
  diff the dispatch overhead may exceed the benefit.
