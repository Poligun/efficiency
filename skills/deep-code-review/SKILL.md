---
name: deep-code-review
description: Reviews a git branch for API design quality, business-logic correctness, and adherence to established repo conventions — the judgment calls compilers, linters, and a line-by-line bug scan can't make. Use this skill whenever the user asks for a deep, thorough, or careful review of their branch or PR, wants feedback on API or proto design, asks whether their changes follow the repo's existing patterns, wants edge cases or business logic scrutinized before merging, or asks "review this properly" / "what's wrong with this design". Trigger on phrases like "deep review", "review my branch", "review this PR", "API design review", "does this match our conventions", "check the edge cases", "is this a good API", "review before I merge", or any request for review that goes beyond finding obvious bugs.
---

# Deep Code Review

You are reviewing a branch for three things a compiler will never tell the author:
whether the API they added is one they'll regret, whether the logic handles the cases
they didn't think of, and whether the code looks like it belongs in this repo.

## What you're doing and why

The built-in `/code-review` already hunts line-level bugs well. What it can't do is
judge *design* — and design review fails in two specific ways that shape everything
below.

It fails by **noise**: a reviewer with no sense of what this repo already does will
invent conventions, cite patterns that don't exist, and bury three real findings under
twenty opinions. So conventions here are *measured*, not assumed (Step 3), and each
aspect only runs if the branch actually touches it (Step 1).

It fails by **hallucination**: an agent that can't verify a claim will assert it
confidently anyway. So every finding is anchored to a line you quote from the current
tree, and adversarially checked before it reaches the report (Step 5).

You are the arbiter, not a router. You read the change first-hand in Steps 2–3 so that
when two agents disagree in Step 6 you can settle it by reading code rather than by
picking whichever one sounded more certain.

## Step 1: Detect scope

```bash
# SKILL_DIR is the directory this SKILL.md lives in — substitute the real path.
python3 "$SKILL_DIR/scripts/scope_detect.py" --pretty
```

The script resolves the trunk (`origin/HEAD` → `origin/main` → `main` → `master`), then
diffs `merge-base..working tree` — a single range covering committed *and* uncommitted
changes. Reviewing before the commit is the common case, and a stray debug line is worth
catching then rather than after it ships.

Read the JSON. It gives you `aspects` (`wire_api`, `code_api`, `logic`, `convention`,
each `active` with a `strength`), a `shape`, per-file `signals` with evidence, and
`notes`.

Exit codes: `2` not a git repo · `3` no trunk found (ask the user for `--base`) · `4`
empty range (say so and stop — there's nothing to review).

**You may widen activation by judgment, never narrow it.** The script is deliberately
conservative; if you can see that a change is architecturally significant in a way the
regexes missed, turn the aspect on and say why. But if it says an aspect is inactive and
you have no positive reason to disagree, trust it — that's the whole point of gating.

Two cases where you should stop early rather than review:

- **All aspects inactive** (a dependency bump, a docs-only change). Skim the diff first —
  enough to say *which* dependency moved and from what to what, since a note naming neither
  is useless — then report and stop. Skip Steps 3–8 entirely and use the short report shape
  in Step 7. Do not manufacture findings to justify the run.
- **`shape: focused`** (small diff). Do the API and convention work inline yourself
  instead of dispatching — delegation costs more than it saves at that size. Still
  dispatch business logic, because keeping it out of your context is the point.

## Step 2: Read the change yourself

```bash
MB=<the merge_base value from the scope JSON>   # don't re-derive it; the script resolved it
git diff --stat "$MB"
git log --oneline "$MB"..HEAD
git diff "$MB" -- '*.proto' '*.graphql' '*.thrift' 'openapi*'   # wire contracts, in full
```

Wire contracts are usually small and are the highest-signal part of a diff — read them
completely. Skim the rest via `--stat`.

Then write a **change thesis**, at most 12 lines: what this branch is for, what it adds,
what it changes about existing behavior, and anything that looks off-topic for the stated
purpose. That last part matters — branches that smuggle an unrelated breaking change past
review are a recurring pattern, and you can only notice it if you've formed a view of what
the branch is *supposed* to be.

## Step 3: Build the convention ledger

Only if `convention` is active. You're establishing what this repo actually does, so a
cheap agent can check against it in Step 4 instead of guessing.

```bash
ls CLAUDE.md AGENTS.md .cursor/rules/ CONTRIBUTING.md 2>/dev/null   # written rules, if any
```

Then probe the patterns the new code would have to match. Grep for how *sibling* modules
do the thing the new module does — module declaration and re-export style, error types,
visibility, test placement, logging. `references/convention-probes.md` has per-language
recipes; read it if the repo isn't one you can probe from memory.

Score every candidate rule and write the ledger:

| Rule | Support | Counterexamples | Verdict |
|---|---|---|---|
| `[what the pattern is]` | `[n files]` | `[n files]` | `established` / `mixed` / `absent` |

**The establishment test**, applied in order — the first rule that matches wins, so every
rule/count combination lands somewhere:

1. Fewer than 3 supporting occurrences → `absent`. Not a convention; no finding, ever.
2. 0 or 1 counterexamples → `established`. Findings allowed.
3. Support-to-counter ratio of at least 3:1 → `established`, but say the counterexamples
   exist when you cite it. A dominant pattern with a couple of holdouts is still the
   pattern, and a widely-followed rule shouldn't be unenforceable because two old files
   predate it.
4. Anything else → `mixed`. An unranked note reading "the repo is inconsistent here",
   never a finding against the author.

This is what lets convention review work in a repo with no CLAUDE.md, and it exists
because the obvious-looking convention is often wrong. If two modules alphabetize their
imports and a third doesn't, "this repo alphabetizes" is a finding the codebase itself
contradicts — and a reviewer who files it loses the author's trust for the other nine.

## Step 4: Dispatch the review agents

Launch every active agent **in a single message** so they run concurrently. Each subagent
gets a fresh context; that's deliberate, so one agent's conclusions can't quietly suppress
another's. Round 1 is at most five agents, which stays inside the harness concurrency cap;
the batching caution in Step 5 is where fan-out actually gets large.

| Agent | When | Model | Role file |
|---|---|---|---|
| A1 wire-contract-reviewer | `wire_api` active | `opus` | `agents/wire-contract-reviewer.md` |
| A2 code-api-reviewer | `code_api` active | `opus` | `agents/code-api-reviewer.md` |
| A3 business-logic-review | `logic` active | `opus` | sibling skill — see below |
| A4 convention-scout | `convention` active | `haiku` | `agents/convention-scout.md` |
| A5 surface-consistency | both API aspects `strong` | `haiku` | `agents/convention-scout.md` §Surface consistency |

The model tiers aren't arbitrary. A1–A3 are open-ended judgment, where a cheap model
produces style-guide platitudes. A4 is the opposite: you hand it a ledger of rules that
are already decided and ask it to find violations. Small models check explicit rules well
and infer them badly, which is exactly why the inferring stayed with you in Step 3.

Give every agent the same five blocks:

```
1. ROLE      — the full contents of agents/<role>.md
2. RANGE     — the literal commands: git diff <merge_base> -- <its files>
               (agents fetch their own diff; don't paste it, your context stays clean)
3. SCOPE     — its file list from aspects.<x>.files, plus: do not report on
               lockfiles, generated files, or files outside this list
4. CONTEXT   — your change thesis (and, for A4 only, the convention ledger)
5. CONTRACT  — the finding schema from references/severity-rubric.md, and that
               aspect's section of references/false-positives.md
```

Pass the false-positive list to *finders*, not just verifiers. A finding never raised
costs nothing to verify.

**Don't wait idly while round 1 runs.** There's no way to block on a subagent, and polling
for one burns tool calls to no purpose. Agents take minutes; use that time for the
first-hand reading Step 6 depends on — open the files behind the riskiest hunks, trace the
call paths the change touches, and settle any convention-ledger rows you left uncertain.
Arbitration is only as good as what you know independently, and this is the window where
that knowledge is free. If you finish before the agents do, read the diff's largest
untouched neighbor: the code that *calls* what changed.

**Dispatching A3:** `business-logic-review` lives at `../business-logic-review/SKILL.md`
relative to this skill. Tell the subagent to read it and run in `mode=subagent`, which
makes it return structured JSON and propose memory rather than writing it. If that file
doesn't exist, say so in the report's Coverage line and run the angle checklist from
`../business-logic-review/references/angles.md` inline — never silently drop the aspect.

**Knowledge base location.** Only if you're actually dispatching A3 — an active `logic`
aspect the user has narrowed away doesn't count, and interrupting someone who asked for a
proto review with a question about directory layout is exactly the wrong trade. When you
are dispatching it, resolve this *before* dispatch, so no subagent stalls on a question it
can't answer:

1. `<repo>/.claude/knowledge/` exists → use it.
2. `~/.claude/projects/<repo-slug>/knowledge/` exists → use it.
3. Neither → ask the user once: knowledge in the repo (committed, teammates and CI agents
   benefit, shows up in PR diffs) or in personal space (private, nobody else gets it).
   Creating the directory *is* the record — there's no config file, so you never re-ask.

If both exist, read both (repo first) and write to the repo. If the user is unavailable —
a non-interactive run — default to reading whatever exists and proposing rather than
writing. Never block a review on this question.

## Step 5: Verify

**Dedup before you verify.** Agents working independently will hand you the same finding
several times over — that's the fan-out working as intended, not a fault. But verification
is the expensive step and its budget is small, so spending it on duplicates is how a real
finding ends up unverified. Run the dedup half of Step 6 first (same anchor within 3 lines,
or the same claim in different words, including across aspects), then verify what's left.
Conflict resolution still happens after, in Step 6, because it needs the verdicts.

Then run one verifier per surviving finding at MEDIUM or above, capped at 12 (severity
order; disclose in Coverage if you hit the cap). LOW findings and design notes skip
verification and are stamped `unverified` — never imply verification that didn't happen.

Dispatch them in **batches of about 5** rather than all at once. Subagent concurrency is
capped by the harness and shared with whatever else is in flight; a batch of 12 partially
fails, and a silently dropped verifier means a finding ships stamped as verified when
nothing checked it. Batching costs a little wall-clock and removes that failure mode.

Model tiers: `haiku` for convention verifiers (settling one by grep), `sonnet` for API and
logic verifiers. Verification is a bounded single-question task, so it doesn't need the
tier the finders used.

Verifiers get `agents/finding-verifier.md`, which carries two verdict vocabularies:

| Finding aspect | Verdict | Uncertainty defaults to |
|---|---|---|
| business logic | `CONFIRMED` / `PLAUSIBLE` / `REFUTED` | **REFUTED** — dropped |
| API design, conventions | `GROUNDED` / `TASTE` / `REFUTED` | **TASTE** — demoted, kept |

The asymmetry is deliberate. A false bug report costs the reader more than a missed one,
because it burns trust in the whole report — so logic findings must earn their place. But
a design observation that can't be *proven* is still often the most valuable thing in a
review; it just belongs below the fold rather than deleted. Scoring design findings on a
confidence scale and filtering the low ones deletes the entire aspect, because a taste
judgment never scores high.

## Step 6: Arbitrate

**Dedup.** Same file with anchors within 3 lines, or the same claim in different words —
including *across* aspects, which happens often. Keep the more specific anchor, union the
evidence, record which agents corroborated.

Corroboration raises confidence one notch and severity zero notches. Independent agents
converging is evidence a finding is *real*; it says nothing about how much it *hurts*.
Conflating the two is how review panels inflate.

**Conflicts.** Three things count: agents taking opposite positions on the same pattern;
incompatible factual claims about the same symbol; severities two or more notches apart
after dedup.

Resolve by reading the code, never by voting. Open the anchor and ±40 lines around it.
For pattern disputes the ledger decides — and a `mixed` verdict means *both sides lose*,
becoming a note about repo inconsistency rather than a finding against the author. For
factual disputes, read and settle; if you genuinely can't settle it from the code, that's
a round-2 trigger, not a coin flip. For severity disputes, assign it yourself: agents
propose severity, only you see the whole change and can judge blast radius.

**Round 2** fires if any of these hold, and runs **at most once**, with at most 2 agents,
each asking one narrow question:

- Arbitration surfaced something in an active aspect that no agent covered.
- Two or more findings from one agent died for the same reason — that agent had a wrong
  mental model, so re-run it with a one-paragraph correction, not a blank re-review.
- A HIGH+ finding needs a fact the diff doesn't contain ("does anything still read this
  field?"). Dispatch one tracer with that single question.
- An aspect at `strength: strong` returned zero findings.

A round-2 agent may resolve, drop, or add at most one finding, and its output goes
through verification but not back through arbitration — so it can't create a conflict that
would justify a round 3. There is no round 3. Anything still open goes in a **"Could not
resolve"** section naming the evidence you'd need. Disclosure closes the loop; another
round doesn't.

That last trigger requires `strong` specifically. Zero findings is a legitimate and
common result, and a reviewer that treats silence as failure will manufacture findings to
fill it.

## Step 7: Write the report

The report is human-facing prose: write it in the house voice, whose rules the installed
tech-writing digest carries, keeping this skill's mandated shapes (severity bands,
finding structure) as specified.

Full rubric in `references/severity-rubric.md` — read it before ranking. In short:
severity is **impact**, fix-clarity is independent, and ordering puts the cheap fixes
first within each severity band so the reader gets momentum before they hit the one that
needs a meeting.

```markdown
# Review: [branch] → [base]

[2-3 sentences: what this branch does, and your overall read. Lead with the thing
that would most change the author's plan.]

**Coverage.** [Which aspects ran and which didn't. Distinguish the two reasons for
skipping — "you asked me to skip X" and "the script found no X to review" mean
different things to a reader deciding whether to run again. Note any caps hit and any
findings that shipped unverified. An unstated gap reads as "we checked everything".]

## Needs a decision before merge
[Only CRITICAL/HIGH findings whose fix requires a human call. Omit the section
entirely if there are none. Each carries its open question.]

## Findings

### F1 — [claim, ≤70 chars] (SEVERITY · fix-clarity · verdict)
`path/to/file.rs:104` [· not yet committed, if applicable]

[2-4 sentences: what's wrong, why it matters, and the concrete consequence.]

```
[the quoted line(s), from the current tree]
```

**Fix.** [What to do. If NEEDS-DECISION, state the question instead.]

## Design notes
[TASTE-verdict observations and `mixed` convention findings. One line each,
unranked. These are opinions, and labelled as such.]

## Could not resolve
[Anything arbitration couldn't settle, with the evidence that would settle it.
Omit if empty.]
```

**If you stopped early at Step 1**, the template above is the wrong shape — it's built for
a run that had findings. Use this instead, and don't pad it:

```markdown
# Review: [branch] → [base]

[1-2 sentences: what this branch is, and why there's nothing to review.]

**Coverage.** [Which aspects were inactive and the reason each was inactive, from the
scope JSON. State the counts — "0 changed lines in source files" is the evidence.]

## Worth knowing before you merge
[Only what the scope script surfaced — major dependency bumps named with their
from/to versions, or a build-contract change. One line each. If there is genuinely
nothing, say so in a sentence and stop; an empty section is a fine outcome.]
```

Write findings that name a consequence, not a category:

> **Instead of:** "The request handler uses string concatenation to build the query.
> Consider using a safer approach."
>
> **Write:** "The `sort` parameter is concatenated into the ORDER BY clause unvalidated,
> so a value of `id; DROP TABLE …` changes the statement's structure rather than its
> sort order — the handler's validation checks that the field is present, not what it
> contains."

The first could have been written without reading the code. The second couldn't — and
that's the difference the author will notice.

Write your own from the code in front of you. An example that gets adapted rather than
re-derived is how a review starts describing a codebase it didn't read.

## Step 8: Offer to post to GitHub

The terminal report is the deliverable. Stop there unless the user wants it posted.

If they do, show exactly what will be posted before posting anything, split into two
groups, because they land differently:

- **Committed findings** → inline review comments, anchored to `path` + `line`.
- **Uncommitted findings** → the summary comment body, under a "Not yet pushed" heading.
  GitHub can only anchor a comment to a blob in the PR diff, and working-tree changes
  don't have one yet.

```bash
gh auth status >/dev/null 2>&1 || echo "GitHub CLI isn't authenticated — run 'gh auth login' first"
gh pr view --json number,headRefOid -q '.number, .headRefOid'
```

Post one comment per finding with `gh`, which works anywhere the CLI is authenticated:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments \
  -f body='...' -f commit_id="$SHA" -f path='src/foo.rs' -F line=104 -f side=RIGHT
```

If your environment exposes a dedicated inline-comment tool (some do, under names like
`create_inline_comment`), prefer it — it handles positioning better. Check what's actually
available rather than assuming either one; the `gh` path is the fallback that always works.

Include a suggestion block only when it fully fixes the issue — a partial suggestion
someone clicks "commit" on is worse than none. Wait for explicit confirmation before the
first call.

## Edge cases

- **No PR exists** — report to the terminal and say posting isn't available; offer to
  create the PR only if the user asks.
- **Detached HEAD or no trunk** — ask for the base ref rather than guessing; a wrong base
  produces a review of someone else's work.
- **Diff is entirely generated code** — say so and stop. Review the source of truth (the
  `.proto`, the schema) instead, if it changed.
- **The branch mixes a feature with unrelated changes** — review both, and say plainly in
  the thesis that they're unrelated. Bundled breaking changes are how they get merged
  unnoticed.
- **An agent returns nothing** — record it in Coverage. Empty is a valid answer, and only
  a `strong` aspect returning empty is worth a second look.
- **The user asks for one aspect only** ("just review the proto", "skip the
  implementation") — honor it, run only that agent, and say in Coverage which aspects you
  skipped at their request. But read the narrowing as constraining **where findings are
  anchored, not what you may read**. Judging whether a contract is honest *requires*
  grepping the implementation for a consumer; a literal reading that forbids opening `src/`
  makes the most valuable API findings unreachable and produces a near-empty report that
  looks like a clean bill of health. Read whatever you need, anchor findings in the files
  the user asked about, and don't report implementation defects they didn't ask for.
- **Uncommitted changes only** — perfectly reviewable; note that nothing can be posted
  inline yet.
