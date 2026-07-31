---
name: business-logic-review
description: Hunts business-logic and edge-case bugs on a git branch — lifecycle gaps, missing deduplication or idempotency, time and ordering boundaries, silent fallback values that invert a decision, partial-failure handling, unvalidated input reaching an interpreter, and declared-but-unwired configuration. Accumulates verified domain knowledge in the reviewed repo so later reviews recall intent instead of guessing it. Use this skill whenever the user asks to check business logic, hunt for logic bugs, review edge cases, ask "what did I miss", verify correctness of a feature branch, or wants to know whether a state machine or workflow handles all its cases. Trigger on phrases like "check the edge cases", "review the logic", "what could go wrong here", "did I handle all the cases", "hunt for bugs in this feature", "is this correct". Also invoked as a subagent by deep-code-review.
---

# Business Logic Review

You are looking for the bugs that survive a compiler, a linter, and a careful line-by-line
read: the ones where every statement is valid and the *behavior* is still wrong.

## What you're doing and why

Mechanical review is solved. Types, nullability, and style have tools. What's left is hard
for exactly one reason: **the reviewer has to know what the code was supposed to do, and
that isn't in the diff.**

A fresh agent handed a diff will fill that gap by inventing intent, then reporting
confidently against its own invention. That's the failure mode this skill is built around,
and it produces two halves that have to be designed together:

- **Angles that don't need intent** (Step 4). A state machine with a transition nobody can
  perform is wrong under *any* intent. A fallback value that inverts a comparison is wrong
  regardless of what the feature was for. Most findable logic bugs are like this, and
  hunting them by name beats hunting them by vibe.
- **Memory that supplies the intent you can't derive** (Steps 2 and 7), under provenance
  rules strict enough that it never becomes a hallucination amplifier.

One rule governs the memory half, and it's worth stating before anything else:

> **Memory stores pointers and questions. It never stores evidence.**

A memory entry tells you where to look and what to ask. The evidence in a finding is
always code you quoted from the current tree, this session. That single constraint is what
makes stale memory survivable — at worst a stale entry wastes a lookup. It cannot produce
a wrong finding.

## Step 1: Scope the review and pick a mode

```bash
# First trunk ref that exists wins. Note the loop rather than an && / || chain —
# `A && echo X || B && echo Y` prints BOTH on success, which silently yields a
# two-line BASE and a merge-base that errors out.
for ref in origin/HEAD origin/main origin/master main master; do
  git rev-parse --verify --quiet "$ref^{commit}" >/dev/null && BASE=$ref && break
done
MB=$(git merge-base "$BASE" HEAD)
git diff --stat "$MB"          # committed AND uncommitted — reviews often run pre-commit
git log --oneline "$MB"..HEAD
```

**Mode matters for your output.** If your prompt says `mode=subagent`, you were dispatched
by `deep-code-review`: return one fenced JSON block and at most one line of prose, and
**never write memory** — return proposals instead. A subagent can't ask the user for
approval, and several sibling agents each writing the same file is a merge conflict by
construction. Otherwise you're talking to a human: markdown, and you handle the memory
approval yourself in Step 7.

## Step 2: Recall what's already known

Skip if no knowledge base exists — but offer to seed one in Step 7.

Locate it: `<repo>/.claude/knowledge/`, else `~/.claude/projects/<repo-slug>/knowledge/`.
If both, read both, repo first.

Read `INDEX.md` **only**. It's a routing table: map your changed file paths to domain
slugs, then load at most two domain files. Loading everything defeats the purpose — the
index exists so recall stays cheap.

Then check whether what you loaded is still true:

```bash
# Which anchor files changed since these claims were recorded?
git log --name-only --pretty=format: <oldest-recorded-sha>..HEAD -- <anchor paths> | sort -u
# Does each claim's anchor quote still exist?
rg -F --line-number "<the quoted anchor text>" <anchor path>
```

Each claim lands in one of four states, and they gate what you're allowed to do with it:

| State | Meaning | You may |
|---|---|---|
| FRESH | anchor file untouched since recorded | use it as a prior — still quote current code in any finding |
| DRIFTED | file changed, quote survives | re-read ±40 lines first; treat the claim as a hypothesis |
| BROKEN | quote is gone | **not cite it at all** this review; re-derive from current code or drop it |
| UNVERIFIABLE | an absence claim | never trusted; re-run its `verify_absence` command every time |

Guard against the obvious trap here: memory primes your questions, it doesn't answer them.
An agent that reads "alerts must deduplicate" and goes looking for confirmation will find
it. Read the code first and let memory tell you *where to look hardest*.

Details in `references/memory-protocol.md` — read it now if you're touching memory at all.

## Step 3: Build the behavior model

Before hunting anything, write 8–15 lines:

```
ENTITIES     [each thing with a lifecycle, and its states]
EFFECTS      [every externally visible thing this code does — notify, write, order,
              publish, charge. These are what a bug actually damages.]
PROMISES     [what the contract, config, docs, and validation say will happen]
TRIGGERS     [what makes this code run, and how often]
```

This isn't ceremony. The angles below are questions asked *of a model* — without one, "are
there lifecycle gaps?" degenerates into pattern-matching on keywords. It's also where this
skill's scope gets defined: **if a finding can't be traced to a promise in the model, it
belongs in a general code review, not here.**

## Step 4: Hunt with named angles

Full hunting procedures, grep seeds, and per-angle false positives are in
`references/angles.md`. Load the sections whose gate fired.

**Six core angles, always run:**

| Angle | The question |
|---|---|
| **A1 Lifecycle** | Build the state × operation matrix. Which transitions can nobody perform? Which states have no exit? What gets created and never released? |
| **A2 Repeat-Fire** | What happens when this runs again and the world hasn't changed? Where's the edge detection, cooldown, or dedup key? |
| **A3 Boundary & Window** | For every window `[a,b]`: who advances `a`, is it inclusive at both ends, how many clocks are involved, what do the first and last iterations look like? |
| **A4 Fallback & Sentinel** | Find every default-on-failure — `unwrap_or`, `??`, catch-and-continue, NaN, `-1`, empty. Trace each into the decision it feeds. Does it flip that decision? |
| **A5 Partial Failure** | What work is abandoned mid-way, what state is left half-updated, does one item's failure kill the batch, and can anyone who could act actually see it? |
| **A6 Declared Surface** | Take every declared field, flag, config key, and doc comment. Grep for a real consumer of each. A declaration with no reader is dead weight or a lie to the caller. |

**Four conditional angles**, run when their gate fires:

| Angle | Gate |
|---|---|
| **A7 Taint** | the diff builds a string that something later interprets — SQL, shell, path, template, expression language |
| **A8 Numeric Domain** | arithmetic on externally-supplied numbers, unit conversion, or float money |
| **A9 Identity & Correlation** | things matched by index, position, or order rather than a stable identifier |
| **A10 Concurrency** | locks, channels, spawns, cancellation, or shared mutable state |

A4 and A6 tend to have the highest yield and the lowest cost — both are close to a grep,
and both find bugs that are invisible in review because the code *looks* defensive. A
fallback that silently substitutes zero for a failed parse reads as careful error handling
right up until you notice it makes a threshold comparison always true.

**Scaling.** Under ~400 changed lines, run the angles as an in-context checklist — one
reviewer holding the whole behavior model beats ten holding fragments. Above that,
dispatch subagents, but **budget for a concurrency cap**: you may be one of several agents
an orchestrator already has in flight, and dispatch can be refused. Send the highest-yield
angles first (A4 and A6 are close to a grep and find the most per token; A1 and A2 need the
behavior model most), and run whatever gets refused inline rather than dropping it. Note in
your output which angles ran which way — a reader can't tell a skipped angle from a
thorough one otherwise.

## Step 5: Verify before you believe yourself

Every finding needs a concrete **execution trace**: specific inputs or state → the exact
wrong output, crash, or corrupted state. Not "this could fail" — *this input produces that
result*.

Write the trace before you write the finding. Most business-logic false positives die
right here, because constructing the trace is when you discover the guard you missed. If
you can't write one, you don't have a finding; you might have a question for Step 7.

Then check the findings ledger (`review/findings/<domain>.md`) for anything already known:

- **Already open?** Reference it rather than re-reporting as new.
- **In the graveyard?** Check whether *all* the refutation's premises still hold at this
  site. If any differ, raise it with the delta stated explicitly. A refutation front-loads
  the question; it doesn't silence it.

**Severity caps by what the finding rests on:**

| Rests on | Cap |
|---|---|
| code or test evidence | none |
| user-confirmed intent | none — quote the human |
| documented intent (a comment, a proto doc) | MEDIUM, and phrase it as a contract mismatch |
| your inference about intent | **not a finding** — it's an open question |

That last row is the anti-hallucination valve. Comments lie, and a comment claiming an
operation is unconditional while the code rejects half its inputs is a *contradiction*
worth reporting — but it's evidence about the contract, not about what the team wanted.

Severity and fix-clarity definitions live in
`../deep-code-review/references/severity-rubric.md`. Use them exactly; the orchestrator
merges your findings with other agents' and the vocabularies have to match.

## Step 6: Report

Both output shapes are in `references/output-contract.md`. Subagent mode returns JSON;
human mode returns markdown with the findings, then two closing sections — the questions
you couldn't answer from the code, and the proposed memory diff.

Write findings with a trace, not a category:

> **Bad:** "This may retry indefinitely. Consider adding a backoff or a retry limit."
>
> No evidence, no trace, no basis for severity — and indistinguishable from a hallucination
> about a retry limit that might exist somewhere you didn't look.
>
> **Good:** "**HIGH — Retries forever on a permanent failure.** `<file>:<lines>` retries
> whenever the call returns an error, and no attempt counter or terminal-error check exists
> anywhere on that path (`rg 'max_retries|attempt|backoff' <dir>/` → no matches). Trace: a
> 404 from the upstream is not retryable, but it takes the same branch as a timeout, so a
> single deleted record produces one request per interval indefinitely — at the configured
> 30s tick, 2,880 requests a day against an endpoint that will never succeed. Fix:
> needs-decision (distinguishing retryable from terminal errors is a product call; the
> error type carries no such distinction today)."

The shape is what matters: a claim, an anchor, a **negative grep that establishes absence**,
a trace with a concrete number, and an honest fix classification. Write your own example
from the code in front of you — never adapt one of these.

## Step 7: Propose the memory update

An entry earns a slot only if **all three** hold: it's non-derivable or expensive to
re-derive · knowing it changes a verdict or a severity · it describes a rule or a shape
rather than a line of code.

What's worth keeping: domain invariants, lifecycle maps, taint sources, confirmed findings,
refuted claims with their guards, and absence claims. What isn't: anything the compiler
enforces, restatements of readable code, style preferences (those are CLAUDE.md material),
and product rationale the team owns (that belongs in `docs/`).

**Provenance is what keeps this honest.** `code`, `test`, and `doc` claims you may write
freely — they're anchored and cheap to re-verify. A `user` claim requires a verbatim quote
of what the human actually said. An `inferred` claim **may not be written as a claim at
all**; it goes to `## Open questions` with a proposed answer and `asked: never`. That's
free to be wrong, costs one line, and hands the next review a ready-made thing to ask.
When the human answers, the question becomes an invariant with their words attached — and
that loop is why this gets better across reviews rather than just longer.

In subagent mode, emit proposals and write nothing. Otherwise show the diff and wait:

```bash
git diff --no-index /dev/null .claude/knowledge/domains/<slug>.md   # for new files
git diff .claude/knowledge/                                         # for edits
```

Schema, staleness mechanics, the graveyard format, and file templates are all in
`references/memory-protocol.md`.

## Edge cases

- **No knowledge base yet** — offer to seed one, but only for domains this review actually
  touched. Never backfill a whole repo speculatively; unverified bulk memory is the thing
  this design exists to prevent.
- **Memory says X, the code clearly does not-X** — the code wins for evidence. Ask whether
  the rule changed. Never file a finding on the strength of memory alone.
- **A user-provenance claim goes BROKEN** — don't delete it. Flip it to
  `needs-reconfirmation` and ask. Losing hard-won intent costs more than one question.
- **Huge diff** — model the feature from its contracts, interfaces, and handlers first,
  then read implementations only along paths an angle flagged.
- **Generated code in the diff** — skip it, review its source of truth instead.
- **Pure refactor, no behavior change** — the highest-yield angle is A6 plus a
  removed-behavior check: for each deleted line, name the invariant it enforced and find
  where the new code re-establishes it.
- **Zero findings in subagent mode** — return the JSON with an empty findings array. Don't
  editorialize, and don't pad.
- **The user declines the memory write** — proceed, don't re-ask this session, and don't
  quietly write it somewhere else.
